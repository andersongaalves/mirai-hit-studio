"""Roadmap 5.15: client contact stays scoped to assigned producers and admin policy."""
import unittest

import test_bootstrap_database as isolated
from test_entrega_final import SETUP as DELIVERY_SETUP

SETUP = DELIVERY_SETUP + '''
with Session(engine) as db:
    customer = db.get(ClienteModel, 1)
    customer.nome = 'Cliente sintético'
    customer.telefone = '(11) 99999-0000'
    db.add_all([
        UsuarioModel(id=3, username='producer-b', password_hash='unused', role='produtor', is_admin=False, ativo=True),
        UsuarioModel(id=8, username='unassigned', password_hash='unused', role='produtor', is_admin=False, ativo=True),
    ])
    stage = db.query(ProducaoEtapaModel).filter_by(producao_id=PRODUCTION_ID).first()
    stage.responsavel_usuario_id = 3
    STAGE_ID = stage.id
    db.commit()
path = f'/portal/produtor/producoes/{PRODUCTION_ID}'
expected = {'nome': 'Cliente sintético', 'email': 'a@example.test', 'whatsapp': '(11) 99999-0000'}
def detail(username):
    return api.get(path, headers=bearer(username))
'''


class ContatoClienteProdutorTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_assignment_and_minimal_detail_only(self):
        self.run_case('''
for username in ('producer-a', 'producer-b'):
    response = detail(username)
    assert response.status_code == 200, response.text
    assert response.json()['contato_cliente'] == expected
    listed = api.get('/portal/produtor/producoes', headers=bearer(username))
    assert listed.status_code == 200
    assert all(row['contato_cliente'] is None for row in listed.json())
assert detail('unassigned').status_code == 404
assert detail('client-a').status_code == 403
assert api.get('/portal/produtor/producoes/9999', headers=bearer('producer-a')).status_code == 404
with Session(engine) as db:
    db.get(ProducaoEtapaModel, STAGE_ID).responsavel_usuario_id = 2
    db.commit()
assert detail('producer-b').status_code == 404
assert detail('producer-a').json()['contato_cliente'] == expected
''')

    def test_admin_can_hide_and_restore_contact(self):
        self.run_case('''
policy_path = f'/producoes/{PRODUCTION_ID}/politicas'
payload = {'politicas': {'produtor_ve_contato_cliente': False}, 'motivo': 'Contato intermediado pelo Admin'}
assert api.put(policy_path, headers=bearer('producer-a'), json=payload).status_code == 403
assert api.put(policy_path, headers=ADMIN, json=payload).status_code == 200
for username in ('producer-a', 'producer-b'):
    response = detail(username)
    assert response.status_code == 200 and response.json()['contato_cliente'] is None
    assert expected['email'] not in response.text and expected['whatsapp'] not in response.text
updated = api.patch(path + '/status', headers=bearer('producer-a'), json={'status': 'em_producao'})
assert updated.status_code == 200 and updated.json()['contato_cliente'] is None, updated.text
assert api.delete(policy_path, headers=ADMIN).status_code == 200
assert detail('producer-b').json()['contato_cliente'] == expected
''')

    def test_missing_or_inactive_customer_never_uses_budget_contacts(self):
        self.run_case('''
with Session(engine) as db:
    customer = db.get(ClienteModel, 1)
    customer.ativo = False
    db.get(OrcamentoModel, 1).whatsapp = '11911112222'
    db.commit()
assert detail('producer-a').json()['contato_cliente'] is None
with Session(engine) as db:
    db.get(OrcamentoModel, 1).cliente_id = None
    db.commit()
assert detail('producer-a').json()['contato_cliente'] is None
''')

    def test_contact_policy_is_frozen_and_privacy_wins_aggregation(self):
        self.run_case('''
assert policies.padroes()['produtor_ve_contato_cliente'] is True
hidden = {**policies.padroes(), 'produtor_ve_contato_cliente': False}
assert policies.agregar({'itens': [{'servico_id': 1, 'politicas': policies.padroes()},
                                  {'servico_id': 2, 'politicas': hidden}]})[
    'produtor_ve_contato_cliente'] is False
assert api.put('/politicas/globais', headers=ADMIN, json={'base_versao': 0, 'politicas': hidden}).status_code == 200
# Existing contracts are immutable: retroactive privacy changes use the admin exception.
assert detail('producer-a').json()['contato_cliente'] == expected
''')
