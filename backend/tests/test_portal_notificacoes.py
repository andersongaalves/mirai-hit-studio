"""Roadmap 5.18: private, transactional and idempotent portal notifications."""
import unittest

import test_bootstrap_database as isolated
from test_entrega_final import SETUP as DELIVERY_SETUP

SETUP = DELIVERY_SETUP + '''
from models import PortalNotificacaoModel
from routers.portal_notificacoes import admin_router as admin_notifications_router
from routers.portal_notificacoes import router as notifications_router
from routers.producao_mensagens import router as messages_router
from services import portal_notificacao_service as notifications
app.include_router(notifications_router)
app.include_router(admin_notifications_router)
app.include_router(messages_router)

def notices(username='client-a'):
    response = api.get('/portal/notificacoes', headers=bearer(username))
    assert response.status_code == 200, response.text
    return response.json()

with Session(engine) as db:
    db.add(ClienteModel(id=2, nome='Cliente B', email='b@example.test'))
    db.flush()
    db.add_all([
        UsuarioModel(id=3, username='producer-b', password_hash='unused', role='produtor', is_admin=False, ativo=True),
        UsuarioModel(id=5, username='client-b', password_hash='unused', role='cliente', is_admin=False, ativo=True, cliente_id=2),
    ])
    db.query(PortalNotificacaoModel).delete()
    db.commit()
'''


class PortalNotificacoesTests(unittest.TestCase):
    def test_metadata_bootstrap_keeps_notification_and_credit_tables_private(self):
        isolated.BootstrapTests().run_case('''
import models
from sqlalchemy import create_mock_engine
emitted = []
mock = create_mock_engine('postgresql://', lambda statement, *args, **kwargs:
    emitted.append(str(statement.compile(dialect=mock.dialect))))
for name in ('portal_notificacoes', 'projeto_creditos'):
    Base.metadata.tables[name].create(mock, checkfirst=False)
    assert any('ALTER TABLE ' + name + ' ENABLE ROW LEVEL SECURITY' in sql for sql in emitted)
    for role in ('anon', 'authenticated'):
        assert any('REVOKE ALL ON TABLE ' + name + ' FROM ' + role in sql for sql in emitted)
        assert any("IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '" + role + "')" in sql for sql in emitted)
for role in ('anon', 'authenticated'):
    assert any('REVOKE ALL ON SEQUENCE public.projeto_creditos_id_seq FROM ' + role in sql for sql in emitted)
''')

    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_upload_versions_visibility_and_seen_claim(self):
        self.run_case('''
first = upload('previa', 'mix.mp3')
with patch.object(producao_arquivo_service, 'new_production_file_storage', return_value=storage):
    response = api.post(f'/portal/produtor/producoes/{PRODUCTION_ID}/arquivos', headers=bearer('producer-a'),
                        data={'tipo': 'previa', 'substitui_arquivo_id': str(first)},
                        files={'arquivo': ('mix-v2.mp3', b'y' * 100, 'audio/mpeg')})
assert response.status_code == 201 and response.json()['versao'] == 2, response.text
second = response.json()['id']
result = notices()
assert result['nao_vistas'] == 2 and len(result['itens']) == 2, result
assert all(item['tipo'] == 'nova_previa' for item in result['itens'])
assert all(item['url'] == f'/cliente/projetos/{PRODUCTION_ID}' for item in result['itens'])
assert not any('mix.mp3' in item['texto'] for item in result['itens'])
assert notices('client-b')['itens'] == []
ids = [item['id'] for item in result['itens']]
claimed = api.post('/portal/notificacoes/vistas', headers=bearer('client-a'), json={'ids': ids})
assert claimed.status_code == 200 and len(claimed.json()) == 2, claimed.text
assert all(item['vista_em'] for item in claimed.json())
assert api.post('/portal/notificacoes/vistas', headers=bearer('client-a'), json={'ids': ids}).json() == []
assert notices()['nao_vistas'] == 0 and len(notices()['itens']) == 2
assert api.post('/portal/notificacoes/vistas', headers=bearer('client-b'), json={'ids': ids}).json() == []
assert api.post('/portal/notificacoes/vistas', headers=bearer('client-a'), json={'ids': [True]}).status_code == 422
assert api.get('/portal/notificacoes', headers=ADMIN).status_code == 403
assert api.get('/portal/notificacoes').status_code == 401
with Session(engine) as db:
    db.get(ProducaoArquivoModel, first).visivel_cliente = False
    db.commit()
assert len(notices()['itens']) == 1
with Session(engine) as db:
    notifications.arquivo_compartilhado(db, db.get(ProducaoArquivoModel, second))
    db.commit()
assert len(notices()['itens']) == 1  # Resharing does not resend the same event.
''')

    def test_messages_are_private_and_assignment_revocation_applies(self):
        self.run_case('''
base = f'/portal/produtor/producoes/{PRODUCTION_ID}/mensagens'
internal = api.post(base, headers=bearer('producer-a'), json={'texto': 'internal secret', 'audiencia': 'equipe'})
assert internal.status_code == 201, internal.text
assert notices()['itens'] == []
public = api.post(base, headers=bearer('producer-a'), json={'texto': '<script>private text</script>', 'audiencia': 'todos'})
assert public.status_code == 201, public.text
assert len(notices()['itens']) == 1 and notices()['itens'][0]['texto'] == 'Nova mensagem na sua produção.'
assert notices('producer-a')['itens'] == []  # Never notify the sender.
reply = api.post(f'/portal/cliente/producoes/{PRODUCTION_ID}/mensagens', headers=bearer('client-a'),
                 json={'texto': 'Feedback'})
assert reply.status_code == 201, reply.text
assert len(notices('producer-a')['itens']) == 1
with Session(engine) as db:
    db.get(ProducaoModel, PRODUCTION_ID).produtor_id = 3
    db.query(ProducaoEtapaModel).filter_by(producao_id=PRODUCTION_ID).update({'responsavel_usuario_id': 3})
    db.commit()
assert notices('producer-a')['itens'] == []
assert notices('producer-b')['itens'] == []  # Reassignment does not disclose another user's history.
''')

    def test_payment_replay_and_delivery_release_do_not_duplicate(self):
        self.run_case('''
delivery = upload('entrega', 'final.wav', 'audio/wav')
with Session(engine) as db:
    # This test seeds its unpaid delivery before notification generation.
    db.query(PortalNotificacaoModel).delete()
    charge = CobrancaModel(proposta_id=PROPOSAL_ID, cliente_id=1, valor_total=Decimal('100.00'),
                           moeda='BRL', status='pendente')
    db.add(charge)
    db.flush()
    charge_id = charge.id
    notifications.arquivo_compartilhado(db, db.get(ProducaoArquivoModel, delivery))
    payment = financial_service.registrar_pagamento(db, charge_id, tipo='entrada', valor=Decimal('50.00'), status='aprovado')
    notifications.pagamento_confirmado(db, payment)
    db.commit()
assert blocked() is True
types = [item['tipo'] for item in notices()['itens']]
assert types.count('nova_entrega') == 1 and types.count('pagamento_confirmado') == 1
assert 'entrega_liberada' not in types
with Session(engine) as db:
    payment = financial_service.registrar_pagamento(db, charge_id, tipo='saldo', valor=Decimal('50.00'), status='aprovado')
    notifications.pagamento_confirmado(db, payment)
    notifications.pagamento_confirmado(db, payment)
    db.commit()
assert blocked() is False
types = [item['tipo'] for item in notices()['itens']]
assert types.count('pagamento_confirmado') == 2 and types.count('entrega_liberada') == 1, types
with Session(engine) as db:
    assert db.query(PagamentoModel).filter_by(cobranca_id=charge_id).count() == 2
''')

    def test_rolled_back_upload_never_notifies(self):
        self.run_case('''
with patch.object(producao_arquivo_service, 'new_production_file_storage', return_value=storage), \\
     patch.object(notifications, 'arquivo_compartilhado', side_effect=RuntimeError('synthetic_failure')):
    try:
        api.post(f'/portal/produtor/producoes/{PRODUCTION_ID}/arquivos', headers=bearer('producer-a'),
                 data={'tipo': 'previa'}, files={'arquivo': ('mix.mp3', b'x' * 100, 'audio/mpeg')})
    except RuntimeError:
        pass
assert notices()['itens'] == []
with Session(engine) as db:
    assert db.query(ProducaoArquivoModel).count() == 0
''')

    def test_stage_visibility_and_reasoned_delivery_exception(self):
        self.run_case('''
with Session(engine) as db:
    production = db.get(ProducaoModel, PRODUCTION_ID)
    admin = db.get(UsuarioModel, 6)
    stage = db.query(ProducaoEtapaModel).filter_by(producao_id=PRODUCTION_ID, nome='Rough Mix').one()
    for status in ('em_andamento', 'em_revisao', 'em_andamento', 'em_revisao', 'concluida'):
        stages.atualizar(db, production, stage.id, papel='admin', usuario=admin, status=status)
types = [item['tipo'] for item in notices()['itens']]
assert types.count('etapa_concluida') == 1 and types.count('revisao_liberada') == 1, types
path = f'/producoes/{PRODUCTION_ID}/politicas'
assert api.put(path, headers=ADMIN, json={'politicas': {'cliente_ve_etapas': False},
                                        'motivo': 'Intermediação administrativa'}).status_code == 200
assert notices()['itens'] == []  # Policy changes also hide historical stage events.
with Session(engine) as db:
    db.add(CobrancaModel(proposta_id=PROPOSAL_ID, cliente_id=1, valor_total=Decimal('100.00'),
                         moeda='BRL', status='pendente'))
    db.commit()
delivery = upload('entrega', 'final.wav', 'audio/wav')
assert blocked() is True
assert api.put(path, headers=ADMIN, json={'politicas': {'entrega_final': 'liberada'},
                                        'motivo': 'Acordo registrado com o cliente'}).status_code == 200
assert blocked() is False
assert [item['tipo'] for item in notices()['itens']].count('entrega_liberada') == 1
assert api.put(path, headers=ADMIN, json={'politicas': {'entrega_final': 'liberada'},
                                        'motivo': 'Acordo registrado com o cliente'}).status_code == 200
assert [item['tipo'] for item in notices()['itens']].count('entrega_liberada') == 1
''')

    def test_incomplete_or_conflicting_payment_never_announces_confirmation(self):
        self.run_case('''
with Session(engine) as db:
    charge = CobrancaModel(proposta_id=PROPOSAL_ID, cliente_id=1, valor_total=Decimal('100.00'),
                           moeda='BRL', status='pendente')
    db.add(charge)
    db.flush()
    payment = financial_service.registrar_pagamento(db, charge.id, tipo='integral', valor=Decimal('100.00'))
    assert db.query(PortalNotificacaoModel).count() == 0
    for status in ('cancelado', 'reembolsado', 'rejeitado'):
        payment.status = status
        notifications.pagamento_confirmado(db, payment)
    payment.status = 'aprovado'
    for reconciliation in ('required', 'conflict'):
        payment.reconciliation_status = reconciliation
        notifications.pagamento_confirmado(db, payment)
    payment.reconciliation_status = None
    charge.cliente_id = 2
    notifications.pagamento_confirmado(db, payment)
    charge.cliente_id = 1
    charge.moeda = 'USD'
    with db.no_autoflush:  # Simulate malformed input without bypassing the database BRL constraint.
        notifications.pagamento_confirmado(db, payment)
        assert db.query(PortalNotificacaoModel).count() == 0
    db.rollback()  # Synthetic malformed rows are never persisted.
assert notices()['itens'] == []
''')

    def test_admin_inbox_is_private_and_skips_test_chains(self):
        self.run_case('''
from models import OrcamentoModel
with Session(engine) as db:
    real = OrcamentoModel(nome_cliente='Cliente', email='lead@example.test', servico='Mix', valor_total=0)
    test = OrcamentoModel(nome_cliente='Teste', email='test@example.test', servico='Mix', valor_total=0, is_test=True)
    db.add_all([real, test]); db.flush()
    notifications.solicitacao_producao(db, real)
    notifications.solicitacao_producao(db, real)  # replay: same event key, one row
    notifications.solicitacao_producao(db, test)
    db.commit()
    real_id = real.id
inbox = api.get('/admin/notificacoes', headers=ADMIN)
assert inbox.status_code == 200, inbox.text
assert [(item['tipo'], item['url']) for item in inbox.json()['itens']] == [
    ('admin_solicitacao_producao', '/admin.html#section-orcamentos')], inbox.json()
assert inbox.json()['nao_vistas'] == 1
assert api.get('/admin/notificacoes', headers=bearer('client-a')).status_code == 403
assert api.get('/admin/notificacoes', headers=bearer('producer-a')).status_code == 403
assert notices()['itens'] == [] and notices('producer-a')['itens'] == []
ids = [item['id'] for item in inbox.json()['itens']]
assert api.post('/portal/notificacoes/vistas', headers=bearer('client-a'), json={'ids': ids}).json() == []
claimed = api.post('/admin/notificacoes/vistas', headers=ADMIN, json={'ids': ids})
assert claimed.status_code == 200 and len(claimed.json()) == 1, claimed.text
assert api.get('/admin/notificacoes', headers=ADMIN).json()['nao_vistas'] == 0
with Session(engine) as db:
    rows = db.query(PortalNotificacaoModel).filter_by(orcamento_id=real_id).all()
    assert rows and {row.papel for row in rows} == {'admin'}  # one per active admin
''')

    def test_additive_migration_roundtrip_does_not_backfill(self):
        isolated.BootstrapTests().run_case('''
from alembic import command
assert bootstrap(engine) == 'f2b4d6e8a0c3'
assert 'portal_notificacoes' in inspect(engine).get_table_names()
with engine.connect() as connection:
    assert connection.exec_driver_sql('SELECT count(*) FROM portal_notificacoes').scalar_one() == 0
command.downgrade(migration_config(), 'f1a3c5e7b902')
assert 'portal_notificacoes' not in inspect(engine).get_table_names()
command.upgrade(migration_config(), 'f3b5d7a9c124')
with engine.connect() as connection:
    assert connection.exec_driver_sql('SELECT count(*) FROM portal_notificacoes').scalar_one() == 0
''')
