"""Roadmap 3.0, 5.06: contract stages instantiated in productions."""
import unittest

import test_bootstrap_database as isolated
from test_proposta_snapshot import SETUP as SNAPSHOT_SETUP

SETUP = SNAPSHOT_SETUP + '''
import os, tempfile
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient
from core.security import create_access_token
from database import get_db
from models import ClienteModel, ProducaoEtapaAtribuicaoModel, ProducaoEtapaModel
from routers.producao_etapas import router as stages_router
from services import producao_etapa_service as stages

def approved_production(db, budget_id=1, items=None):
    proposal = service.criar_por_orcamento(db, budget_id)
    proposal = service.atualizar(db, proposal.id, PropostaUpdate(itens=items or CATALOG_ITEMS))
    with patch.object(resend.Emails, 'send', return_value={'id': f'message-{budget_id}'}):
        commercial.enviar(db, proposal.id)
    commercial.aprovar(db, proposal.id)
    return crud_producao.buscar_por_orcamento(db, budget_id), proposal

def make_api():
    with Session(engine) as db:
        db.add_all([ClienteModel(id=1, nome='Cliente A', email='a@example.test'),
                    ClienteModel(id=2, nome='Cliente B', email='b@example.test')])
        db.flush()
        db.add_all([
            UsuarioModel(id=2, username='producer-a', password_hash='unused', role='produtor', is_admin=False, ativo=True),
            UsuarioModel(id=3, username='producer-b', password_hash='unused', role='produtor', is_admin=False, ativo=True),
            UsuarioModel(id=4, username='client-a', password_hash='unused', role='cliente', is_admin=False, ativo=True, cliente_id=1),
            UsuarioModel(id=5, username='client-b', password_hash='unused', role='cliente', is_admin=False, ativo=True, cliente_id=2),
            UsuarioModel(id=6, username='admin', password_hash='unused', role='admin', is_admin=True, ativo=True),
        ])
        db.get(OrcamentoModel, 1).cliente_id = 1
        db.commit()
    app = FastAPI()
    app.include_router(stages_router)
    from routers.portal_produtor import router as producer_router
    from routers.producao_mensagens import router as messages_router
    app.include_router(producer_router)
    app.include_router(messages_router)
    def session():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = session
    return TestClient(app)

def bearer(username):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': username, 'av': 0})}
'''


class ProducaoEtapasTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_stages_are_instantiated_from_the_frozen_snapshot(self):
        self.run_case('''
with Session(engine) as db:
    seed_service(db)
    before = datetime.now(timezone.utc)
    production, proposal = approved_production(db)
    created = stages._etapas(db, production.id)
    assert [(s.ordem, s.ordem_no_item, s.nome, s.valor, s.status) for s in created] == [
        (1, 1, 'Briefing', Decimal('0.00'), 'pendente'),
        (2, 2, 'Rough Mix', Decimal('160.00'), 'pendente'),
        (3, 3, 'Mixagem', Decimal('400.00'), 'pendente'),
        (4, 4, 'Masterizacao', Decimal('240.00'), 'pendente'),
    ]
    assert sum(s.valor for s in created) == Decimal('800.00')  # Free line (R$ 50) has no stages.
    assert all(s.item_indice == 1 and s.servico_id == 1 and s.proposta_id == proposal.id for s in created)
    assert all(s.responsavel_usuario_id == production.produtor_id for s in created)
    assert created[0].administrativa and created[0].prazo is None
    assert not created[0].depende_da_anterior and created[2].depende_da_anterior
    # Deadlines accumulate inside the item from the release moment (3 + 3 + 3 days).
    offsets = [(s.prazo.replace(tzinfo=timezone.utc) - before).days for s in created[1:]]
    assert offsets == [2, 5, 8] or offsets == [3, 6, 9], offsets
    # Idempotent, and later catalog edits never touch instantiated stages.
    assert stages.instanciar(db, production, db.get(PropostaModel, proposal.id)) == created
    db.get(ServicoModel, 1).etapas[1].nome = 'Outro nome'
    db.commit()
    assert [s.nome for s in stages._etapas(db, production.id)][1] == 'Rough Mix'
    assert db.query(ProducaoEtapaModel).count() == 4
''')

    def test_transitions_permissions_dependencies_and_progress(self):
        self.run_case('''
client = make_api()  # Users first: producer 2 is the budget's producer.
with Session(engine) as db:
    seed_service(db)
    db.get(OrcamentoModel, 1).produtor_id = 2  # Stages start assigned to producer-a (5.07).
    db.commit()
    production, _ = approved_production(db)
    production_id = production.id
base_admin = f'/producoes/{production_id}/etapas-contratuais'
base_producer = f'/portal/produtor/producoes/{production_id}/etapas'
base_client = f'/portal/cliente/producoes/{production_id}/etapas'

view = client.get(base_client, headers=bearer('client-a'))
assert view.status_code == 200, view.text
body = view.json()
assert body['progresso_percentual'] == 0 and len(body['etapas']) == 4
assert all(not ({'valor', 'peso_percentual', 'acoes', 'responsavel_usuario_id'} & set(stage)) for stage in body['etapas'])

producer = client.get(base_producer, headers=bearer('producer-a')).json()
ids = [stage['id'] for stage in producer['etapas']]
assert [stage['acoes'] for stage in producer['etapas']] == [['em_andamento'], ['em_andamento'], [], []]
assert all('valor' not in stage for stage in producer['etapas'])

def patch(base, stage, user, **body):
    return client.patch(f'{base}/{stage}', headers=bearer(user), json=body)

blocked = patch(base_producer, ids[2], 'producer-a', status='em_andamento', status_atual='pendente')
assert blocked.status_code == 409 and 'Rough Mix' in blocked.json()['detail']
assert patch(base_producer, ids[1], 'producer-a', status='em_andamento', status_atual='pendente').status_code == 200
# Producers cannot approve (conclude); stale state is a conflict.
assert patch(base_producer, ids[1], 'producer-a', status='concluida', status_atual='em_andamento').status_code == 422
assert patch(base_producer, ids[1], 'producer-a', status='em_revisao', status_atual='pendente').status_code == 409
assert patch(base_producer, ids[1], 'producer-a', status='em_revisao', status_atual='em_andamento').status_code == 200
assert patch(base_producer, ids[1], 'producer-a', status='em_revisao', status_atual='em_revisao', prazo=None).status_code == 422
done = patch(base_admin, ids[1], 'admin', status='concluida', status_atual='em_revisao')
assert done.status_code == 200, done.text
assert done.json()['progresso_percentual'] == 20  # R$ 160 of R$ 800.
admin_stage = done.json()['etapas'][1]
assert admin_stage['status'] == 'concluida' and admin_stage['concluida_em'] and admin_stage['valor'] == '160.00'
assert done.json()['etapas'][2]['acoes'] == ['em_andamento']

# Mixing starts; reopening Rough Mix is then blocked until Mixing goes back to pending.
assert patch(base_producer, ids[2], 'producer-a', status='em_andamento', status_atual='pendente').status_code == 200
reopen = patch(base_admin, ids[1], 'admin', status='em_andamento', status_atual='concluida')
assert reopen.status_code == 409 and 'Mixagem' in reopen.json()['detail']
assert patch(base_admin, ids[2], 'admin', status='pendente', status_atual='em_andamento').status_code == 200
reopened = patch(base_admin, ids[1], 'admin', status='em_andamento', status_atual='concluida')
assert reopened.status_code == 200 and reopened.json()['etapas'][1]['concluida_em'] is None
assert reopened.json()['progresso_percentual'] == 0

deadline = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
moved = patch(base_admin, ids[3], 'admin', prazo=deadline)
assert moved.status_code == 200 and moved.json()['etapas'][3]['prazo'].startswith(deadline[:10])
assert patch(base_admin, ids[3], 'admin').status_code == 422
assert patch(base_admin, ids[3], 'admin', status='em_andamento').status_code == 422

# Ownership and roles.
assert client.get(base_producer, headers=bearer('producer-b')).status_code == 404
assert patch(base_producer, ids[0], 'producer-b', status='em_andamento', status_atual='pendente').status_code == 404
assert client.get(base_client, headers=bearer('client-b')).status_code == 404
assert client.get(base_admin, headers=bearer('producer-a')).status_code == 403
assert client.get(base_client, headers=bearer('producer-a')).status_code == 403
assert client.get(base_client).status_code == 401
assert patch(base_producer, 9999, 'producer-a', status='em_andamento', status_atual='pendente').status_code == 404

with Session(engine) as db:
    actions = [event.action for event in db.query(AuditLogModel).order_by(AuditLogModel.id)]
    assert actions.count('production.stage_status_changed') == 6, actions
    assert actions.count('production.stage_deadline_changed') == 1
    stage = db.get(ProducaoEtapaModel, ids[1])
    assert stage.iniciada_em is not None and stage.status == 'em_andamento'
''')

    def test_generate_for_productions_created_before_506(self):
        self.run_case('''
with Session(engine) as db:
    seed_service(db)
    production, _ = approved_production(db)
    free, _ = approved_production(db, 2, items=[{'descricao': 'Avulso', 'quantidade': 1, 'valor_unitario': '90.00'}])
    assert stages._etapas(db, free.id) == []
    # Simulates a production from before 5.06: no stages and no assignment history.
    db.query(ProducaoEtapaAtribuicaoModel).filter(ProducaoEtapaAtribuicaoModel.producao_id == production.id).delete()
    db.query(ProducaoEtapaModel).filter(ProducaoEtapaModel.producao_id == production.id).delete()
    db.commit()
    production_id, free_id = production.id, free.id
client = make_api()
listing = client.get(f'/producoes/{production_id}/etapas-contratuais', headers=bearer('admin')).json()
assert listing['etapas'] == [] and listing['pode_gerar'] is True
assert client.get(f'/producoes/{free_id}/etapas-contratuais', headers=bearer('admin')).json()['pode_gerar'] is False
generated = client.post(f'/producoes/{production_id}/etapas-contratuais/gerar', headers=bearer('admin'))
assert generated.status_code == 200, generated.text
assert [stage['nome'] for stage in generated.json()['etapas']] == ['Briefing', 'Rough Mix', 'Mixagem', 'Masterizacao']
assert generated.json()['pode_gerar'] is False
assert client.post(f'/producoes/{production_id}/etapas-contratuais/gerar', headers=bearer('admin')).status_code == 409
assert client.post(f'/producoes/{free_id}/etapas-contratuais/gerar', headers=bearer('admin')).status_code == 422
assert client.post('/producoes/9999/etapas-contratuais/gerar', headers=bearer('admin')).status_code == 404
assert client.post(f'/producoes/{production_id}/etapas-contratuais/gerar', headers=bearer('producer-a')).status_code == 403
''')


    def test_stage_owners_assignment_history_and_isolation(self):
        self.run_case('''
os.environ.setdefault('RATE_LIMIT_DB', os.path.join(tempfile.mkdtemp(), 'limits.sqlite3'))
client = make_api()
with Session(engine) as db:
    seed_service(db)
    db.get(OrcamentoModel, 1).produtor_id = 2  # producer-a coordinates the production.
    db.commit()
    production, _ = approved_production(db)
    production_id = production.id
    assert production.produtor_id == 2
    initial = db.query(ProducaoEtapaAtribuicaoModel).order_by(ProducaoEtapaAtribuicaoModel.id).all()
    assert [(row.novo_usuario_id, row.motivo) for row in initial] == [(2, 'Atribuicao inicial')] * 4
admin_base = f'/producoes/{production_id}/etapas-contratuais'
producer_base = f'/portal/produtor/producoes/{production_id}/etapas'
ids = [stage['id'] for stage in client.get(admin_base, headers=bearer('admin')).json()['etapas']]

def assign(stage, user_id, current, reason=''):
    return client.patch(f'{admin_base}/{stage}/responsavel', headers=bearer('admin'),
                        json={'responsavel_usuario_id': user_id, 'responsavel_atual': current, 'motivo': reason})

# Before any assignment producer-b sees nothing of this production.
assert client.get(f'/portal/produtor/producoes/{production_id}', headers=bearer('producer-b')).status_code == 404
assert client.get(producer_base, headers=bearer('producer-b')).status_code == 404
assert [item['id'] for item in client.get('/portal/produtor/producoes', headers=bearer('producer-b')).json()] == []

assert assign(ids[2], 3, 3).status_code == 409  # Stale current responsible.
assert assign(ids[2], 4, 2).status_code == 422  # A client is not a producer.
assert assign(ids[2], 6, 2).status_code == 422  # Neither is an admin.
moved = assign(ids[2], 3, 2, 'Mixagem com especialista')
assert moved.status_code == 200, moved.text
assert moved.json()['etapas'][2]['responsavel_nome'] == 'producer-b'

# producer-b now reaches the production as a stage owner, not as coordinator.
listed = client.get('/portal/produtor/producoes', headers=bearer('producer-b')).json()
assert [(item['id'], item['coordenador']) for item in listed] == [(production_id, False)]
assert client.get(f'/portal/produtor/producoes/{production_id}', headers=bearer('producer-a')).json()['coordenador'] is True
assert client.get(f'/portal/produtor/producoes/{production_id}/arquivos', headers=bearer('producer-b')).status_code == 200
assert client.get(f'/portal/produtor/producoes/{production_id}/mensagens', headers=bearer('producer-b')).status_code == 200
status_change = client.patch(f'/portal/produtor/producoes/{production_id}/status', headers=bearer('producer-b'),
                             json={'status': 'em_producao'})
assert status_change.status_code == 403

view_b = client.get(producer_base, headers=bearer('producer-b')).json()['etapas']
assert [(stage['minha'], stage['responsavel_rotulo']) for stage in view_b] == [
    (False, 'Outro produtor'), (False, 'Outro produtor'), (True, 'Voce'), (False, 'Outro produtor')]
assert all(stage['acoes'] == [] for stage in view_b)  # Mixing still waits for Rough Mix.
assert all('responsavel_usuario_id' not in stage and 'responsavel_nome' not in stage for stage in view_b)
view_a = client.get(producer_base, headers=bearer('producer-a')).json()['etapas']
assert [stage['minha'] for stage in view_a] == [True, True, False, True]

def patch(user, stage, **body):
    return client.patch(f'{producer_base}/{stage}', headers=bearer(user), json=body)

assert patch('producer-a', ids[1], status='em_andamento', status_atual='pendente').status_code == 200
assert patch('producer-a', ids[1], status='em_revisao', status_atual='em_andamento').status_code == 200
done = client.patch(f'{admin_base}/{ids[1]}', headers=bearer('admin'), json={'status': 'concluida', 'status_atual': 'em_revisao'})
assert done.status_code == 200 and done.json()['etapas'][1]['executor_nome'] == 'producer-a'
# The coordinator gets no power over another owner's stage.
assert patch('producer-a', ids[2], status='em_andamento', status_atual='pendente').status_code == 403
assert client.get(producer_base, headers=bearer('producer-a')).json()['etapas'][2]['acoes'] == []
assert patch('producer-b', ids[2], status='em_andamento', status_atual='pendente').status_code == 200

# Concluded stages keep who executed them.
blocked = assign(ids[1], 3, 2)
assert blocked.status_code == 409 and 'executou' in blocked.json()['detail']
# Reassigning an in-progress stage keeps its status; producer-b loses access with no stage left.
back = assign(ids[2], 2, 3, 'Retorno ao coordenador')
assert back.status_code == 200 and back.json()['etapas'][2]['status'] == 'em_andamento'
assert client.get(f'/portal/produtor/producoes/{production_id}', headers=bearer('producer-b')).status_code == 404
assert client.get(f'/portal/produtor/producoes/{production_id}/arquivos', headers=bearer('producer-b')).status_code == 404
assert assign(ids[3], None, 2).json()['etapas'][3]['responsavel_usuario_id'] is None

history = client.get(f'{admin_base}/{ids[2]}/historico', headers=bearer('admin'))
assert history.status_code == 200, history.text
assert [(row['anterior_nome'], row['novo_nome'], row['atribuido_por_nome'], row['motivo']) for row in history.json()] == [
    (None, 'producer-a', None, 'Atribuicao inicial'),
    ('producer-a', 'producer-b', 'admin', 'Mixagem com especialista'),
    ('producer-b', 'producer-a', 'admin', 'Retorno ao coordenador'),
]
assert client.get(f'{admin_base}/{ids[2]}/historico', headers=bearer('producer-a')).status_code == 403
assert client.get(f'{admin_base}/9999/historico', headers=bearer('admin')).status_code == 404
with Session(engine) as db:
    actions = [event.action for event in db.query(AuditLogModel)]
    assert actions.count('production.stage_assigned') == 3
''')


if __name__ == "__main__":
    unittest.main()
