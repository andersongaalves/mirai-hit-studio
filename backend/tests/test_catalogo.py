"""Catalog rework (after 5.10): typed limits, duration per track and combos sold like services."""
import unittest

import test_bootstrap_database as isolated
from test_cotas_arquivo import SETUP as QUOTAS_SETUP

SETUP = QUOTAS_SETUP + '''
import io, json, wave
from models import ProducaoEtapaModel, ServicoCotaArquivoModel, ServicoModel
from routers.combos import public_router as combos_public_router
from routers.combos import router as combos_router
from routers.servicos import router as services_router
from schemas.servico_estrutura import ler
for extra in (services_router, combos_router, combos_public_router):
    app.include_router(extra)

def wav(seconds):
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(1)
        audio.setframerate(1000)
        audio.writeframes(b'\\x80' * int(seconds * 1000))
    return buffer.getvalue()

def service_payload(**extra):
    payload = {'nome': 'Plano Start', 'subtitulo': '', 'valor_base': 1000, 'aplica_desconto': False,
               'parametros': 'duracao,revisoes', 'estrutura_servico': json.dumps({'intro': '', 'sections': [], 'benefits': []})}
    payload.update(extra)
    return payload
'''


class CatalogoTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_limits_quotas_reviews_and_duration(self):
        self.run_case('''
legacy = {'intro': 'Mix', 'sections': [{'icon': '', 'title': 'Detalhes', 'items': [
    '1 artista', 'Até 2 canais', 'Até 3 minutos', '1 revisão', 'Instrumentos eletrônicos']}], 'benefits': ['Atendimento']}
saved = api.put('/servicos/1', headers=ADMIN, json=service_payload(estrutura_servico=json.dumps(legacy, ensure_ascii=False)))
assert saved.status_code == 200, saved.text
estrutura = json.loads(saved.json()['estrutura_servico'])
assert estrutura == {'versao': 2, 'intro': 'Mix', 'destaques': ['Instrumentos eletrônicos', 'Atendimento'],
                     'limites': {'faixas': 2, 'duracao_min': 3, 'revisoes': 1, 'melodias': None, 'artistas': 1}}
assert saved.json()['categoria'] == 'Mix'  # The editor no longer sends a category; the stored one stays.
with Session(engine) as db:
    quota = db.query(ServicoCotaArquivoModel).filter_by(servico_id=1, tipo='material').one()
    assert (quota.max_arquivos, quota.max_duracao_min) == (2, 3)
bad = api.put('/servicos/1', headers=ADMIN, json=service_payload(estrutura_servico=json.dumps(
    {'versao': 2, 'limites': {'faixas': 0}})))
assert bad.status_code == 422
created = api.post('/servicos', headers=ADMIN, json=service_payload(nome='Letra'))
assert created.status_code == 200 and created.json()['categoria'] == 'avulso'

with Session(engine) as db:
    p = service.atualizar(db, service.criar_por_orcamento(db, 1).id, PropostaUpdate(itens=CATALOG_ITEMS))
    with patch.object(resend.Emails, 'send', return_value={'id': 'synthetic-message'}):
        sent = commercial.enviar(db, p.id)
    stages = sent.snapshot_economico.itens[0].etapas
    assert [stage.revisoes_incluidas for stage in stages] == [None, None, None, 1]  # Reviews: last stage only.
    assert sent.snapshot_economico.itens[0].cotas_arquivos[0].max_duracao_min == 3
    commercial.aprovar(db, p.id)
    production_id = crud_producao.buscar_por_orcamento(db, 1).id
    last = db.query(ProducaoEtapaModel).filter_by(producao_id=production_id).order_by(ProducaoEtapaModel.ordem.desc()).first()
    assert last.revisoes_incluidas == 1

storage = MemoryStorage()
path = f'/portal/cliente/producoes/{production_id}/arquivos'
def send(name, data, mime):
    return api.post(path, headers=bearer('client-a'), data={'tipo': 'material'}, files={'arquivo': (name, data, mime)})
with patch.object(producao_arquivo_service, 'new_production_file_storage', return_value=storage):
    long_track = send('longa.wav', wav(200), 'audio/wav')
    assert long_track.status_code == 422 and '3 min' in long_track.json()['detail'], long_track.text
    broken = send('quebrada.wav', b'x' * 2000, 'audio/wav')
    assert broken.status_code == 422 and 'duracao' in broken.json()['detail'], broken.text
    assert send('voz.wav', wav(170), 'audio/wav').status_code == 201
    assert send('letra.pdf', b'%PDF-1.4 synthetic', 'application/pdf').status_code == 201  # No duration for PDFs.
    third = send('backing.wav', wav(30), 'audio/wav')
    assert third.status_code == 409 and '2 arquivo' in third.json()['detail'], third.text

# Clearing the limits removes the derived quota (other quota fields would be kept).
cleared = api.put('/servicos/1', headers=ADMIN, json=service_payload(estrutura_servico=json.dumps(
    {'versao': 2, 'intro': '', 'destaques': [], 'limites': {}})))
assert cleared.status_code == 200, cleared.text
with Session(engine) as db:
    assert db.query(ServicoCotaArquivoModel).filter_by(servico_id=1).count() == 0
assert ler('{"broken') == ler(None)
''')

    def test_combos_are_sold_like_services(self):
        self.run_case('''
with Session(engine) as db:
    seed_service(db, service_id=2)
    db.get(ServicoModel, 2).parametros = 'pessoas,revisoes'
    db.commit()
api.put('/servicos/1', headers=ADMIN, json=service_payload(estrutura_servico=json.dumps(
    {'versao': 2, 'intro': 'Mix', 'destaques': ['Atendimento'], 'limites': {'faixas': 5, 'duracao_min': 3}})))
payload = {'nome': 'Launch', 'descricao': 'Do beat ao master.', 'subtitulo': 'Tudo pronto', 'preco_base': '220.00',
           'aplica_desconto': True, 'destaques': ['  Desconto de combo ', ''], 'servicos': [1, 2]}
combo = api.post('/combos', headers=ADMIN, json=payload)
assert combo.status_code == 201, combo.text
body = combo.json()
assert (body['subtitulo'], body['aplica_desconto'], body['destaques']) == ('Tudo pronto', True, ['Desconto de combo'])
assert body['parametros'] == 'duracao,revisoes,pessoas'
assert body['servicos'][0]['estrutura']['limites']['faixas'] == 5
assert api.post('/combos', headers=ADMIN, json={**payload, 'destaques': ['x' * 201]}).status_code == 422
inactive = api.post('/combos', headers=ADMIN, json={**payload, 'nome': 'Antigo', 'ativo': False})
assert inactive.status_code == 201
assert api.get('/combos').status_code in (401, 403)  # The admin list stays private.
public = api.get('/catalogo/combos')
assert public.status_code == 200 and [item['nome'] for item in public.json()] == ['Launch']
''')


if __name__ == "__main__":
    unittest.main()
