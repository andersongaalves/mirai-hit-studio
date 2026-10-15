"""Roadmap 3.0, 5.14: final delivery released only after the balance is paid."""
import unittest

import test_bootstrap_database as isolated
from test_politicas import SETUP as POLICIES_SETUP

SETUP = POLICIES_SETUP + '''
from decimal import Decimal
from models import CobrancaModel, PagamentoModel
from services import financial_service
from services import portal_cliente_service as client_portal

with Session(engine) as db:
    p = service.atualizar(db, service.criar_por_orcamento(db, 1).id, PropostaUpdate(itens=CATALOG_ITEMS))
    with patch.object(resend.Emails, 'send', return_value={'id': 'synthetic-message'}):
        commercial.enviar(db, p.id)
    commercial.aprovar(db, p.id)
    PROPOSAL_ID = p.id
    PRODUCTION_ID = crud_producao.buscar_por_orcamento(db, 1).id

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

# A cancelled charge never holds the delivery.
with Session(engine) as db:
    db.query(PagamentoModel).filter_by(cobranca_id=charge_id).delete()
    db.get(CobrancaModel, charge_id).status = 'pendente'
    db.commit()
assert blocked() is True
with Session(engine) as db:
    db.get(CobrancaModel, charge_id).status = 'cancelada'
    db.commit()
assert blocked() is False

# The producer always reaches its own delivery, whatever the balance.
with Session(engine) as db:
    db.get(CobrancaModel, charge_id).status = 'pendente'
    db.commit()
with patch.object(producao_arquivo_service, 'new_production_file_storage', return_value=storage):
    own = api.get(f'/portal/produtor/arquivos/{delivery_id}/conteudo', headers=bearer('producer-a'))
assert own.status_code == 200, own.text
''')


if __name__ == "__main__":
    unittest.main()
