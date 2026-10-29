"""Roadmap 3.0, 5.14: final delivery released only after the balance is paid."""
import unittest

import test_bootstrap_database as isolated
from test_politicas import SETUP as POLICIES_SETUP

SETUP = POLICIES_SETUP + '''
import socket
from decimal import Decimal
from models import CobrancaModel, PagamentoModel
from services import financial_service
from services import portal_cliente_service as client_portal

# Windows' event loop creates an internal loopback socket; external traffic stays forbidden.
original_connect = network_guard.temp_original
network_guard.stop()
def loopback_only(sock, address):
    if isinstance(address, tuple) and address[0] in {'127.0.0.1', '::1'}:
        return original_connect(sock, address)
    raise AssertionError('external network forbidden')
patch.object(socket.socket, 'connect', loopback_only).start()

with Session(engine) as db:
    p = service.atualizar(db, service.criar_por_orcamento(db, 1).id, PropostaUpdate(itens=[
        {**CATALOG_ITEMS[0], 'valor_unitario': '100.00', 'desconto': '0.00'}]))
    with patch.object(resend.Emails, 'send', return_value={'id': 'synthetic-message'}):
        commercial.enviar(db, p.id)
    commercial.aprovar(db, p.id)
    PROPOSAL_ID = p.id
    PRODUCTION_ID = crud_producao.buscar_por_orcamento(db, 1).id
    # Model a historical, unbilled production; individual cases seed their own charge.
    db.delete(db.query(CobrancaModel).filter_by(proposta_id=p.id).one())
    db.commit()

storage = MemoryStorage()
def upload(kind, name, mime='audio/mpeg'):
    with patch.object(producao_arquivo_service, 'new_production_file_storage', return_value=storage):
        response = api.post(f'/portal/produtor/producoes/{PRODUCTION_ID}/arquivos', headers=bearer('producer-a'),
                            data={'tipo': kind}, files={'arquivo': (name, b'x' * 100, mime)})
    assert response.status_code == 201, response.text
    file_id = response.json()['id']
    with Session(engine) as db:
        model = db.get(ProducaoArquivoModel, file_id)
        model.visivel_cliente = True
        db.commit()
    return file_id

def client_files():
    response = api.get(f'/portal/cliente/producoes/{PRODUCTION_ID}/arquivos', headers=bearer('client-a'))
    assert response.status_code == 200, response.text
    return {item['id']: item for item in response.json()}

def download(file_id):
    with patch.object(producao_arquivo_service, 'new_production_file_storage', return_value=storage):
        return api.get(f'/portal/cliente/arquivos/{file_id}/conteudo', headers=bearer('client-a'))

def blocked():
    with Session(engine) as db:
        return client_portal.entrega_bloqueada(db, db.get(ProducaoModel, PRODUCTION_ID))
'''
SETUP = SETUP.replace('from models import ProducaoEtapaModel,',
                      'from models import ProducaoArquivoModel, ProducaoEtapaModel,', 1)
SETUP += '''
from models import ProducaoEntregaFinalModel
from services import producao_entrega_service
'''


class EntregaFinalTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_policy_default_and_aggregation(self):
        self.run_case('''
assert policies.padroes()['entrega_final'] == 'apos_quitacao'
liberada = {**policies.padroes(), 'entrega_final': 'liberada'}
# Contracts frozen before 5.14 have no key: they get the system default (held until paid).
assert policies._completas({'financeiro_cliente': 'resumido'})['entrega_final'] == 'apos_quitacao'
# With several services the option most favourable to the client wins.
assert policies.agregar({'itens': [{'indice': 1, 'servico_id': 1, 'politicas': policies.padroes()},
                                   {'indice': 2, 'servico_id': 2, 'politicas': liberada}]})['entrega_final'] == 'liberada'
assert api.put('/servicos/1/politicas', headers=ADMIN, json={'entrega_final': 'nunca'}).status_code == 422
assert api.put('/servicos/1/politicas', headers=ADMIN, json={'entrega_final': 'liberada'}).status_code == 422
assert api.put('/politicas/globais', headers=ADMIN, json={
    'base_versao': 0, 'politicas': liberada}).status_code == 422
''')

    def test_structured_instrumental_delivery_is_complete_private_and_payment_gated(self):
        self.run_case('''
payload = {
    'request_id': '550e8400-e29b-41d4-a716-446655440000',
    'categoria': 'instrumental',
    'titulo': 'Instrumental final',
    'multitrack_url': 'https://drive.example.test/private-delivery',
    'observacao': 'Versao aprovada.',
}
files = {
    'arquivo_principal': ('final.mp3', b'mp3-final', 'audio/mpeg'),
    'wav': ('final.wav', b'wav-final', 'audio/wav'),
    'licenca': ('licenca.pdf', b'%PDF-1.4 synthetic', 'application/pdf'),
}
with patch.object(producao_entrega_service, 'new_production_file_storage', return_value=storage):
    created = api.post(f'/portal/produtor/producoes/{PRODUCTION_ID}/entregas-finais',
                       headers=bearer('producer-a'), data=payload, files=files)
assert created.status_code == 201, created.text
delivery = created.json()
assert delivery['categoria'] == 'instrumental'
assert delivery['multitrack_disponivel'] is True and 'multitrack_url' not in delivery
assert delivery['arquivo_principal']['nome_exibicao'] == 'final.mp3'
assert delivery['wav_arquivo']['nome_exibicao'] == 'final.wav'
assert delivery['licenca_arquivo']['nome_exibicao'] == 'licenca.pdf'
with Session(engine) as db:
    assert db.query(ProducaoEntregaFinalModel).count() == 1
    assert db.query(ProducaoArquivoModel).filter_by(producao_id=PRODUCTION_ID, tipo='entrega').count() == 3

# Idempotent retry returns the same package and does not duplicate objects.
with patch.object(producao_entrega_service, 'new_production_file_storage', return_value=storage):
    retried = api.post(f'/portal/produtor/producoes/{PRODUCTION_ID}/entregas-finais',
                       headers=bearer('producer-a'), data=payload, files=files)
assert retried.status_code == 201 and retried.json()['id'] == delivery['id']
with Session(engine) as db:
    assert db.query(ProducaoArquivoModel).filter_by(producao_id=PRODUCTION_ID, tipo='entrega').count() == 3
changed_files = {**files, 'arquivo_principal': ('final.mp3', b'changed-mp3', 'audio/mpeg')}
with patch.object(producao_entrega_service, 'new_production_file_storage', return_value=storage):
    conflict = api.post(f'/portal/produtor/producoes/{PRODUCTION_ID}/entregas-finais',
                        headers=bearer('producer-a'), data=payload, files=changed_files)
assert conflict.status_code == 409
with Session(engine) as db:
    assert db.query(ProducaoArquivoModel).filter_by(producao_id=PRODUCTION_ID, tipo='entrega').count() == 3

listed = api.get(f'/portal/cliente/producoes/{PRODUCTION_ID}/entregas-finais', headers=bearer('client-a'))
assert listed.status_code == 200 and listed.json()[0]['bloqueado_pagamento'] is False
link = api.get(f"/portal/cliente/entregas-finais/{delivery['id']}/multitrack", headers=bearer('client-a'))
assert link.status_code == 200 and link.json()['url'].startswith('https://drive.example.test/')

with Session(engine) as db:
    db.add(CobrancaModel(proposta_id=PROPOSAL_ID, cliente_id=1, valor_total=Decimal('100.00'), moeda='BRL', status='pendente'))
    db.commit()
blocked_list = api.get(f'/portal/cliente/producoes/{PRODUCTION_ID}/entregas-finais', headers=bearer('client-a')).json()
assert blocked_list[0]['bloqueado_pagamento'] is True
assert api.get(f"/portal/cliente/entregas-finais/{delivery['id']}/multitrack", headers=bearer('client-a')).status_code == 402
with patch.object(producao_arquivo_service, 'new_production_file_storage', return_value=storage):
    assert api.get(f"/portal/cliente/arquivos/{delivery['licenca_arquivo']['id']}/conteudo",
                   headers=bearer('client-a')).status_code == 402

with Session(engine) as db:
    db.add(ClienteModel(id=2, nome='Cliente B', email='b@example.test'))
    db.add(UsuarioModel(id=7, username='client-b', password_hash='unused', role='cliente',
                       is_admin=False, ativo=True, cliente_id=2))
    db.commit()
assert api.get(f'/portal/cliente/producoes/{PRODUCTION_ID}/entregas-finais', headers=bearer('client-b')).status_code == 404
assert api.get(f"/portal/cliente/entregas-finais/{delivery['id']}/multitrack", headers=bearer('client-b')).status_code == 404
''')

    def test_instrumental_requires_wav_multitrack_and_pdf_license(self):
        self.run_case('''
with patch.object(producao_entrega_service, 'new_production_file_storage', return_value=storage):
    invalid = api.post(f'/portal/produtor/producoes/{PRODUCTION_ID}/entregas-finais',
        headers=bearer('producer-a'),
        data={'request_id':'550e8400-e29b-41d4-a716-446655440001','categoria':'instrumental','titulo':'Incompleta'},
        files={'arquivo_principal':('final.mp3',b'mp3','audio/mpeg')})
assert invalid.status_code == 422, invalid.text
with Session(engine) as db:
    assert db.query(ProducaoEntregaFinalModel).count() == 0
    assert db.query(ProducaoArquivoModel).filter_by(tipo='entrega').count() == 0
''')

    def test_delivery_held_until_paid(self):
        self.run_case('''
preview_id = upload('previa', 'mix.mp3')
delivery_id = upload('entrega', 'master.wav', 'audio/wav')

# No charge (legacy production): nothing is held.
assert blocked() is False
assert client_files()[delivery_id]['bloqueado_pagamento'] is False

with Session(engine) as db:
    db.add(CobrancaModel(proposta_id=PROPOSAL_ID, cliente_id=1, valor_total=Decimal('100.00'), moeda='BRL',
                         status='pendente'))
    db.commit()
    charge_id = db.query(CobrancaModel).filter_by(proposta_id=PROPOSAL_ID).one().id

files = client_files()
assert files[delivery_id]['bloqueado_pagamento'] is True and files[preview_id]['bloqueado_pagamento'] is False
held = download(delivery_id)
assert held.status_code == 402 and 'quitação do saldo' in held.json()['detail'], held.text
assert download(preview_id).status_code == 200  # Previews stay free.

# Down payment only: still held.
with Session(engine) as db:
    financial_service.registrar_pagamento(db, charge_id, tipo='entrada', valor=Decimal('50.00'), status='aprovado')
    db.commit()
assert blocked() is True and download(delivery_id).status_code == 402

# Admin exception with a reason releases it; removing it goes back to the contract.
path = f'/producoes/{PRODUCTION_ID}/politicas'
exc = api.put(path, headers=ADMIN, json={'politicas': {'entrega_final': 'liberada'}, 'motivo': 'Cliente recorrente'})
assert exc.status_code == 200 and exc.json()['origens']['entrega_final'] == 'excecao', exc.text
assert client_files()[delivery_id]['bloqueado_pagamento'] is False and download(delivery_id).status_code == 200
assert api.delete(path, headers=ADMIN).status_code == 200
assert download(delivery_id).status_code == 402

# Balance paid: released automatically, computed live.
with Session(engine) as db:
    financial_service.registrar_pagamento(db, charge_id, tipo='saldo', valor=Decimal('50.00'), status='aprovado')
    db.commit()
assert client_files()[delivery_id]['bloqueado_pagamento'] is False
released = download(delivery_id)
assert released.status_code == 200 and released.content == b'x' * 100

# Cancellation does not establish settlement and cannot release an unpaid delivery.
with Session(engine) as db:
    db.query(PagamentoModel).filter_by(cobranca_id=charge_id).delete()
    db.get(CobrancaModel, charge_id).status = 'pendente'
    db.commit()
assert blocked() is True
with Session(engine) as db:
    db.get(CobrancaModel, charge_id).status = 'cancelada'
    db.commit()
assert blocked() is True and download(delivery_id).status_code == 402

# The producer always reaches its own delivery, whatever the balance.
with Session(engine) as db:
    db.get(CobrancaModel, charge_id).status = 'pendente'
    db.commit()
with patch.object(producao_arquivo_service, 'new_production_file_storage', return_value=storage):
    own = api.get(f'/portal/produtor/arquivos/{delivery_id}/conteudo', headers=bearer('producer-a'))
assert own.status_code == 200, own.text
''')

    def test_identity_reconciliation_and_refund_fail_closed(self):
        self.run_case('''
delivery_id = upload('entrega', 'final.wav', 'audio/wav')
with Session(engine) as db:
    charge = CobrancaModel(proposta_id=PROPOSAL_ID, cliente_id=1, valor_total=Decimal('100.00'),
                           moeda='BRL', status='pendente')
    db.add(charge)
    db.flush()
    charge_id = charge.id
    financial_service.registrar_pagamento(db, charge_id, tipo='integral', valor=Decimal('100.00'), status='aprovado')
    db.commit()
assert download(delivery_id).status_code == 200
with Session(engine) as db:
    payment = db.query(PagamentoModel).filter_by(cobranca_id=charge_id).one()
    payment.reconciliation_status = 'conflict'
    db.commit()
assert blocked() is True and download(delivery_id).status_code == 402
with Session(engine) as db:
    payment = db.query(PagamentoModel).filter_by(cobranca_id=charge_id).one()
    payment.reconciliation_status = None
    payment.status = 'reembolsado'
    db.commit()
assert blocked() is True and download(delivery_id).status_code == 402
with Session(engine) as db:
    db.query(PagamentoModel).filter_by(cobranca_id=charge_id).one().status = 'aprovado'
    db.add(ClienteModel(id=2, nome='Cliente B', email='b@example.test'))
    db.get(CobrancaModel, charge_id).cliente_id = 2
    db.commit()
assert blocked() is True and download(delivery_id).status_code == 402
with Session(engine) as db:
    db.get(CobrancaModel, charge_id).cliente_id = 1
    db.query(PagamentoModel).filter_by(cobranca_id=charge_id).one().valor = Decimal('101.00')
    db.commit()
assert blocked() is True and download(delivery_id).status_code == 402
''')

    def test_only_authorized_admin_can_record_a_reasoned_exception(self):
        self.run_case('''
delivery_id = upload('entrega', 'final.wav', 'audio/wav')
with Session(engine) as db:
    db.add(CobrancaModel(proposta_id=PROPOSAL_ID, cliente_id=1, valor_total=Decimal('100.00'),
                         moeda='BRL', status='pendente'))
    db.commit()
path = f'/producoes/{PRODUCTION_ID}/politicas'
payload = {'politicas': {'entrega_final': 'liberada'}, 'motivo': 'Acordo comercial registrado'}
for user in ('client-a', 'producer-a'):
    assert api.put(path, headers=bearer(user), json=payload).status_code == 403
assert api.put(path, headers=ADMIN, json={**payload, 'motivo': '    '}).status_code == 422
assert download(delivery_id).status_code == 402
assert api.put(path, headers=ADMIN, json=payload).status_code == 200
assert download(delivery_id).status_code == 200
from models.audit_log import AuditLogModel
with Session(engine) as db:
    event = db.query(AuditLogModel).filter_by(action='production.policies_exception_set').one()
    assert event.actor_user_id == 6 and event.entity_id == str(PRODUCTION_ID)
    assert 'entrega_final' in event.metadata_json['policy_keys']
    assert db.get(ProducaoPoliticaModel, PRODUCTION_ID).motivo == payload['motivo']
assert api.delete(path, headers=ADMIN).status_code == 200
assert download(delivery_id).status_code == 402
with Session(engine) as db:
    db.add(ClienteModel(id=2, nome='Cliente B', email='b@example.test'))
    db.add(UsuarioModel(id=7, username='client-b', password_hash='unused', role='cliente',
                       is_admin=False, ativo=True, cliente_id=2))
    db.commit()
assert api.get(f'/portal/cliente/arquivos/{delivery_id}/conteudo', headers=bearer('client-b')).status_code == 404
assert api.get(f'/portal/cliente/producoes/{PRODUCTION_ID}/arquivos', headers=bearer('client-b')).status_code == 404
''')


if __name__ == "__main__":
    unittest.main()
