"""Roadmap 3.0, 5.09: contractual file quotas (catalog -> snapshot -> production -> upload)."""
import unittest

import test_bootstrap_database as isolated
from test_proposta_snapshot import SETUP as SNAPSHOT_SETUP

SETUP = SNAPSHOT_SETUP + '''
import os, tempfile
os.environ.setdefault('RATE_LIMIT_DB', os.path.join(tempfile.mkdtemp(), 'limits.sqlite3'))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from core.security import create_access_token
from database import get_db
from models import ClienteModel, ProducaoCotaArquivoModel
from routers.cotas_arquivo import router as quotas_router
from routers.portal_cliente import router as client_router
from routers.portal_operacao_admin import router as admin_operation_router
from routers.portal_produtor import router as producer_router
from services import cota_arquivo_service as quotas
from services import producao_arquivo_service
from services.producao_arquivo_storage import ProducaoArquivoStorageError

class MemoryStorage:
    def __init__(self):
        self.objects = {}
        self.counter = 0
    def save(self, data, mime_type):
        self.counter += 1
        key = f'arquivos/{self.counter:032x}/{(self.counter + 100):032x}'
        self.objects[key] = data
        return key
    def read(self, key):
        if key not in self.objects:
            raise ProducaoArquivoStorageError('missing')
        return self.objects[key]
    def delete(self, key):
        self.objects.pop(key, None)

MB = 1024 * 1024
with Session(engine) as db:
    seed_service(db)
    db.add(ClienteModel(id=1, nome='Cliente A', email='a@example.test'))
    db.flush()
    db.add_all([
        UsuarioModel(id=2, username='producer-a', password_hash='unused', role='produtor', is_admin=False, ativo=True),
        UsuarioModel(id=4, username='client-a', password_hash='unused', role='cliente', is_admin=False, ativo=True, cliente_id=1),
        UsuarioModel(id=6, username='admin', password_hash='unused', role='admin', is_admin=True, ativo=True),
    ])
    budget = db.get(OrcamentoModel, 1)
    budget.cliente_id = 1
    budget.produtor_id = 2
    db.commit()

app = FastAPI()
for router in (quotas_router, client_router, producer_router, admin_operation_router):
    app.include_router(router)
def session():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = session
api = TestClient(app)
def bearer(username):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': username, 'av': 0})}
ADMIN = bearer('admin')
'''


class CotasArquivoTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_contract_aggregation(self):
        self.run_case('''
s1 = [{'tipo': 'previa', 'max_arquivos': 2, 'max_versoes': 3, 'max_tamanho_mb': 10, 'max_total_mb': 100,
       'formatos': ['audio/wav']},
      {'tipo': 'entrega', 'max_arquivos': 1, 'max_versoes': None, 'max_tamanho_mb': None, 'max_total_mb': None,
       'formatos': None}]
s2 = [{'tipo': 'previa', 'max_arquivos': 1, 'max_versoes': 5, 'max_tamanho_mb': 20, 'max_total_mb': None,
       'formatos': ['audio/mpeg']}]
snapshot = {'itens': [
    {'indice': 1, 'servico_id': 1, 'quantidade': '2', 'cotas_arquivos': s1},
    {'indice': 2, 'servico_id': None, 'quantidade': '1'},  # Free line: never limits anything.
    {'indice': 3, 'combo_id': 9, 'quantidade': '1.5', 'componentes': [{'servico_id': 2, 'cotas_arquivos': s2}]},
]}
assert quotas.agregar(snapshot) == [{
    'tipo': 'previa', 'max_arquivos': 6, 'max_total_mb': None, 'max_versoes': 5, 'max_tamanho_mb': 20,
    'formatos': ['audio/mpeg', 'audio/wav'],
}]  # 2x2 + 2x1 files (1.5 rounds up); 'entrega' is only in one service, so it has no contractual limit.
assert quotas.agregar({'itens': [{'indice': 1, 'servico_id': 1, 'quantidade': '1'}]}) == []  # Before 5.09.
assert quotas.agregar({'itens': [{'indice': 1, 'servico_id': 1, 'quantidade': '80', 'cotas_arquivos': s1}]})[0][
    'max_arquivos'] == 100  # Capped at the table limit.
''')

    def test_catalog_contract_and_upload_limits(self):
        self.run_case('''
base = '/servicos/1/cotas-arquivos'
assert api.get(base, headers=bearer('producer-a')).status_code == 403
for invalid in [
    {'cotas': [{'tipo': 'previa', 'formatos': ['image/png']}]},
    {'cotas': [{'tipo': 'previa'}, {'tipo': 'previa'}]},
    {'cotas': [{'tipo': 'comprovante'}]},
    {'cotas': [{'tipo': 'previa', 'max_tamanho_mb': 60}]},
]:
    assert api.put(base, headers=ADMIN, json=invalid).status_code == 422, invalid
assert api.put('/servicos/999/cotas-arquivos', headers=ADMIN, json={'cotas': []}).status_code == 404
saved = api.put(base, headers=ADMIN, json={'cotas': [
    {'tipo': 'material', 'max_arquivos': 2, 'max_total_mb': 1},
    {'tipo': 'previa', 'max_arquivos': 1, 'max_versoes': 2, 'max_tamanho_mb': 1, 'formatos': ['audio/mpeg']},
]})
assert saved.status_code == 200, saved.text
assert [cota['tipo'] for cota in saved.json()] == ['material', 'previa']

with Session(engine) as db:
    p = service.atualizar(db, service.criar_por_orcamento(db, 1).id, PropostaUpdate(itens=CATALOG_ITEMS))
    with patch.object(resend.Emails, 'send', return_value={'id': 'synthetic-message'}):
        sent = commercial.enviar(db, p.id)
    frozen = sent.snapshot_economico.itens[0].cotas_arquivos
    assert [(cota.tipo, cota.max_arquivos) for cota in frozen] == [('material', 2), ('previa', 1)]
    commercial.aprovar(db, p.id)
    production = crud_producao.buscar_por_orcamento(db, 1)
    production_id = production.id
    rows = db.query(ProducaoCotaArquivoModel).filter_by(producao_id=production_id).all()
    assert sorted((row.tipo, row.origem) for row in rows) == [('material', 'contrato'), ('previa', 'contrato')]
# Catalog edits after the contract do not change the production.
assert api.put(base, headers=ADMIN, json={'cotas': []}).status_code == 200

storage = MemoryStorage()
def upload(user, path, tipo, name, mime, size, replaces=None):
    data = {'tipo': tipo}
    if replaces:
        data['substitui_arquivo_id'] = str(replaces)
    return api.post(path, headers=bearer(user), data=data, files={'arquivo': (name, b'x' * size, mime)})
producer_path = f'/portal/produtor/producoes/{production_id}/arquivos'
client_path = f'/portal/cliente/producoes/{production_id}/arquivos'
with patch.object(producao_arquivo_service, 'new_production_file_storage', return_value=storage):
    first = upload('producer-a', producer_path, 'previa', 'mix.mp3', 'audio/mpeg', 1000)
    assert first.status_code == 201, first.text
    second = upload('producer-a', producer_path, 'previa', 'outra.mp3', 'audio/mpeg', 1000)
    assert second.status_code == 409 and '1 arquivo' in second.json()['detail'], second.text
    wrong_format = upload('producer-a', producer_path, 'previa', 'mix.wav', 'audio/wav', 1000)
    assert wrong_format.status_code == 422 and 'Formato' in wrong_format.json()['detail']
    too_big = upload('producer-a', producer_path, 'previa', 'mix.mp3', 'audio/mpeg', MB + 1, replaces=first.json()['id'])
    assert too_big.status_code == 422 and '1 MB' in too_big.json()['detail']
    v2 = upload('producer-a', producer_path, 'previa', 'mix-v2.mp3', 'audio/mpeg', 1000, replaces=first.json()['id'])
    assert v2.status_code == 201, v2.text
    v3 = upload('producer-a', producer_path, 'previa', 'mix-v3.mp3', 'audio/mpeg', 1000, replaces=v2.json()['id'])
    assert v3.status_code == 409 and '2 versao' in v3.json()['detail']
    # 'entrega' has no contractual quota: only the global limits apply.
    assert upload('producer-a', producer_path, 'entrega', 'final.wav', 'audio/wav', 1000).status_code == 201

    assert upload('client-a', client_path, 'material', 'voz.wav', 'audio/wav', 600 * 1024).status_code == 201
    space = upload('client-a', client_path, 'material', 'voz2.wav', 'audio/wav', 600 * 1024)
    assert space.status_code == 409 and 'Espaco contratado' in space.json()['detail']
    # The admin is the authority: no contractual limit on its uploads.
    admin_upload = api.post(f'/producoes/{production_id}/arquivos', headers=ADMIN,
                            data={'tipo': 'previa', 'visivel_produtor': 'true', 'visivel_cliente': 'true'},
                            files={'arquivo': ('extra.wav', b'x' * 1000, 'audio/wav')})
    assert admin_upload.status_code == 201, admin_upload.text

client_view = api.get(f'/portal/cliente/producoes/{production_id}/cotas-arquivos', headers=bearer('client-a')).json()
assert [(cota['tipo'], cota['arquivos_usados'], cota['total_usado_bytes']) for cota in client_view['cotas']] == [
    ('material', 1, 600 * 1024)]
producer_view = api.get(f'/portal/produtor/producoes/{production_id}/cotas-arquivos', headers=bearer('producer-a')).json()
assert [(cota['tipo'], cota['arquivos_usados'], cota['max_versoes']) for cota in producer_view['cotas']] == [
    ('previa', 2, 2)]  # The admin's extra file also counts as a logical file.
assert api.get(f'/producoes/{production_id}/cotas-arquivos', headers=bearer('client-a')).status_code == 403

# Admin exception: more preview files for this production only.
changed = api.put(f'/producoes/{production_id}/cotas-arquivos', headers=ADMIN, json={'cotas': [
    {'tipo': 'previa', 'max_arquivos': 3, 'max_versoes': 2, 'formatos': ['audio/mpeg', 'audio/wav']}]})
assert changed.status_code == 200, changed.text
assert [(cota['tipo'], cota['origem']) for cota in changed.json()['cotas']] == [('previa', 'admin')]
with patch.object(producao_arquivo_service, 'new_production_file_storage', return_value=storage):
    assert upload('producer-a', producer_path, 'previa', 'nova.wav', 'audio/wav', 1000).status_code == 201
    # Material lost its quota with the override: global limits only.
    assert upload('client-a', client_path, 'material', 'voz2.wav', 'audio/wav', 600 * 1024).status_code == 201
with Session(engine) as db:
    actions = [event.action for event in db.query(AuditLogModel)]
    assert actions.count('service.file_quotas_updated') == 2
    assert actions.count('production.file_quotas_updated') == 1
''')


if __name__ == "__main__":
    unittest.main()
