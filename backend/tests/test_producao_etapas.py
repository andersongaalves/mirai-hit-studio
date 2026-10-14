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
from models import ClienteModel, ProducaoEtapaModel
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
client = make_api()  # Users first: the production is reassigned to producer 2 below.
with Session(engine) as db:
    seed_service(db)
    production, _ = approved_production(db)
    production.produtor_id = 2
    db.commit()
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


if __name__ == "__main__":
    unittest.main()
