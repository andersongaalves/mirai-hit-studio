"""Roadmap 3.0, 5.10: contractual portal policies (global -> service -> contract -> exception)."""
import unittest

import test_bootstrap_database as isolated
from test_cotas_arquivo import SETUP as QUOTAS_SETUP

SETUP = QUOTAS_SETUP + '''
from models import ProducaoEtapaModel, ProducaoModel, ProducaoPoliticaModel, ServicoEtapaModel, UsuarioModel
from routers.politicas import router as policies_router
from routers.producao_etapas import router as stages_router
from services import politica_service as policies
from services import producao_etapa_service as stages
app.include_router(policies_router)
app.include_router(stages_router)
'''


class PoliticasTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_contract_aggregation_favours_the_client(self):
        self.run_case('''
strict = {'publicacao_previa': 'aprovacao_admin', 'revisoes_excedentes': 'exigir_admin', 'cliente_ve_etapas': False,
          'cliente_ve_prazos_etapas': False, 'financeiro_cliente': 'resumido'}
loose = policies.padroes()
assert policies.agregar({'itens': [{'indice': 1, 'servico_id': 1, 'politicas': strict}]}) == strict
mixed = {'itens': [
    {'indice': 1, 'servico_id': 1, 'politicas': strict},
    {'indice': 2, 'servico_id': None},  # Free line: no policies.
    {'indice': 3, 'combo_id': 4, 'componentes': [{'servico_id': 2, 'politicas': {**strict, 'cliente_ve_etapas': True}}]},
]}
assert policies.agregar(mixed) == {**strict, 'cliente_ve_etapas': True}
assert policies.agregar({'itens': [{'indice': 1, 'servico_id': 1, 'politicas': strict},
                                   {'indice': 2, 'servico_id': 2, 'politicas': loose}]}) == loose
assert policies.agregar({'itens': [{'indice': 1, 'servico_id': 1}]}) is None  # Before 5.10.
# A stored value that no longer validates falls back to the system default for that key only.
assert policies._completas({'publicacao_previa': 'nunca', 'financeiro_cliente': 'resumido', 'x': 1}) == {
    **loose, 'financeiro_cliente': 'resumido'}
''')

    def test_inheritance_enforcement_and_exception(self):
        self.run_case('''
glob = api.get('/politicas/globais', headers=ADMIN).json()
assert glob['versao'] == 0 and glob['politicas'] == glob['padroes'] == policies.padroes()
assert api.get('/politicas/globais', headers=bearer('producer-a')).status_code == 403
v1 = api.put('/politicas/globais', headers=ADMIN, json={'base_versao': 0, 'politicas': {
    **policies.padroes(), 'cliente_ve_prazos_etapas': False}})
assert v1.status_code == 200 and v1.json()['versao'] == 1, v1.text
stale = api.put('/politicas/globais', headers=ADMIN, json={'base_versao': 0, 'politicas': policies.padroes()})
assert stale.status_code == 409
assert api.put('/politicas/globais', headers=ADMIN, json={'base_versao': 1, 'politicas': {
    **policies.padroes(), 'financeiro_cliente': 'oculto'}}).status_code == 422
v2 = api.put('/politicas/globais', headers=ADMIN, json={'base_versao': 1, 'politicas': policies.padroes()}).json()
v3 = api.post('/politicas/globais/restaurar', headers=ADMIN, json={'versao': 1, 'base_versao': 2}).json()
assert v3['versao'] == 3 and v3['politicas']['cliente_ve_prazos_etapas'] is False
assert v3['versoes'][0]['restaurada_de_versao'] == 1

base = '/servicos/1/politicas'
assert api.put(base, headers=ADMIN, json={'publicacao_previa': 'sempre'}).status_code == 422
assert api.put(base, headers=ADMIN, json={'desligar_auditoria': True}).status_code == 422
assert api.put('/servicos/999/politicas', headers=ADMIN, json={}).status_code == 404
saved = api.put(base, headers=ADMIN, json={'publicacao_previa': 'aprovacao_admin',
                                           'revisoes_excedentes': 'exigir_admin', 'financeiro_cliente': 'resumido'})
assert saved.status_code == 200, saved.text
assert saved.json()['politicas'] == {'publicacao_previa': 'aprovacao_admin', 'revisoes_excedentes': 'exigir_admin',
                                     'financeiro_cliente': 'resumido'}
assert saved.json()['herdadas']['cliente_ve_prazos_etapas'] is False

with Session(engine) as db:
    rough = db.query(ServicoEtapaModel).filter_by(servico_id=1, nome='Rough Mix').one()
    rough.revisoes_incluidas = 1
    db.commit()
    p = service.atualizar(db, service.criar_por_orcamento(db, 1).id, PropostaUpdate(itens=CATALOG_ITEMS))
    with patch.object(resend.Emails, 'send', return_value={'id': 'synthetic-message'}):
        sent = commercial.enviar(db, p.id)
    assert sent.snapshot_economico.itens[0].politicas.publicacao_previa == 'aprovacao_admin'
    assert sent.snapshot_economico.itens[1].politicas is None  # Free line.
    commercial.aprovar(db, p.id)
    production_id = crud_producao.buscar_por_orcamento(db, 1).id
    assert db.get(ProducaoPoliticaModel, production_id).contrato == {
        'publicacao_previa': 'aprovacao_admin', 'revisoes_excedentes': 'exigir_admin', 'cliente_ve_etapas': True,
        'cliente_ve_prazos_etapas': False, 'financeiro_cliente': 'resumido'}
    assert policies.detalhar(db, 999)['origens'] == {key: 'global' for key in policies.CHAVES}  # No contract.

# Later global and catalog edits never change the contract in force.
assert api.put('/politicas/globais', headers=ADMIN, json={'base_versao': 3, 'politicas': policies.padroes()}).status_code == 200
assert api.put(base, headers=ADMIN, json={}).status_code == 200
detail = api.get(f'/producoes/{production_id}/politicas', headers=ADMIN).json()
assert detail['vigentes']['publicacao_previa'] == 'aprovacao_admin' and set(detail['origens'].values()) == {'contrato'}

# Previews wait for the admin; deliveries keep their visibility rules.
storage = MemoryStorage()
with patch.object(producao_arquivo_service, 'new_production_file_storage', return_value=storage):
    preview = api.post(f'/portal/produtor/producoes/{production_id}/arquivos', headers=bearer('producer-a'),
                       data={'tipo': 'previa'}, files={'arquivo': ('mix.mp3', b'x' * 100, 'audio/mpeg')})
assert preview.status_code == 201 and preview.json()['visivel_cliente'] is False, preview.text
assert api.get(f'/portal/cliente/producoes/{production_id}/arquivos', headers=bearer('client-a')).json() == []

# Client: stage deadlines hidden by the contract; summary finance view.
client_stages = api.get(f'/portal/cliente/producoes/{production_id}/etapas', headers=bearer('client-a')).json()
assert client_stages['etapas'] and all(stage['prazo'] is None for stage in client_stages['etapas'])
assert 'revisoes_usadas' not in client_stages['etapas'][0] or client_stages['etapas'][0]['revisoes_usadas'] is None
finance = api.get(f'/portal/cliente/producoes/{production_id}/financeiro', headers=bearer('client-a'))
assert finance.status_code == 200, finance.text
if finance.json()['cobranca'] is not None:
    assert finance.json()['resumido'] is True and finance.json()['cobranca']['pagamentos'] == []

# Reviews: the producer returns a stage from review once (included); the second needs the admin.
with Session(engine) as db:
    production = db.get(ProducaoModel, production_id)
    producer = db.get(UsuarioModel, 2)
    admin = db.get(UsuarioModel, 6)
    stage = db.query(ProducaoEtapaModel).filter_by(producao_id=production_id, nome='Rough Mix').one()
    stage_id = stage.id
    for status in ('em_andamento', 'em_revisao', 'em_andamento', 'em_revisao'):
        stages.atualizar(db, production, stage_id, papel='produtor', usuario=producer, status=status)
    view = stages.listar(db, production, papel='produtor', usuario=producer)
    rough_view = next(item for item in view['etapas'] if item['id'] == stage_id)
    assert rough_view['revisoes_usadas'] == 1 and rough_view['acoes'] == [] and view['revisoes_excedentes'] == 'exigir_admin'
    try:
        stages.atualizar(db, production, stage_id, papel='produtor', usuario=producer, status='em_andamento')
    except stages.EtapaConflito as error:
        assert 'revisao extra' in str(error)
    else:
        raise AssertionError('extra review allowed to the producer')
    stages.atualizar(db, production, stage_id, papel='admin', usuario=admin, status='em_andamento')
    assert db.get(ProducaoEtapaModel, stage_id).revisoes_usadas == 2
    rounds = [event.metadata_json for event in db.query(AuditLogModel)
              .filter_by(action='production.stage_status_changed') if 'review_round' in event.metadata_json]
    assert [(item['review_round'], item['extra_review']) for item in rounds] == [(1, False), (2, True)]

# Admin exception: needs a reason and at least one key; removable back to the contract.
path = f'/producoes/{production_id}/politicas'
assert api.put(path, headers=ADMIN, json={'politicas': {}, 'motivo': 'Cliente antigo'}).status_code == 422
assert api.put(path, headers=ADMIN, json={'politicas': {'cliente_ve_etapas': False}, 'motivo': 'ok'}).status_code == 422
assert api.put(path, headers=bearer('producer-a'), json={'politicas': {'cliente_ve_etapas': False},
                                                         'motivo': 'Pedido do cliente'}).status_code == 403
exc = api.put(path, headers=ADMIN, json={'politicas': {'revisoes_excedentes': 'permitir', 'cliente_ve_etapas': False},
                                         'motivo': 'Cliente antigo, revisoes liberadas'})
assert exc.status_code == 200, exc.text
body = exc.json()
assert body['origens']['revisoes_excedentes'] == 'excecao' and body['origens']['publicacao_previa'] == 'contrato'
assert body['motivo'] == 'Cliente antigo, revisoes liberadas'
hidden = api.get(f'/portal/cliente/producoes/{production_id}/etapas', headers=bearer('client-a')).json()
assert hidden['etapas'] == [] and hidden['etapas_ocultas'] is True and 'progresso_percentual' in hidden
with Session(engine) as db:
    production = db.get(ProducaoModel, production_id)
    stages.atualizar(db, production, stage_id, papel='produtor', usuario=db.get(UsuarioModel, 2), status='em_revisao')
    stages.atualizar(db, production, stage_id, papel='produtor', usuario=db.get(UsuarioModel, 2), status='em_andamento')
    assert db.get(ProducaoEtapaModel, stage_id).revisoes_usadas == 3
removed = api.delete(path, headers=ADMIN)
assert removed.status_code == 200 and removed.json()['excecao'] is None
assert set(removed.json()['origens'].values()) == {'contrato'}
assert api.delete(path, headers=ADMIN).status_code == 404
with Session(engine) as db:
    actions = [event.action for event in db.query(AuditLogModel)]
    assert actions.count('policy.global_published') == 3 and actions.count('policy.global_restored') == 1
    assert actions.count('service.policies_updated') == 2
    assert actions.count('production.policies_exception_set') == 1
    assert actions.count('production.policies_exception_removed') == 1
''')


if __name__ == "__main__":
    unittest.main()
