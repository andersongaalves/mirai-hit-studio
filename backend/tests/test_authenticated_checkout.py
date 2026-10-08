"""Authenticated proposal checkout contracts on a disposable database."""
import unittest

import test_bootstrap_database as isolated
from test_mercado_pago import MP_SETUP


SETUP = MP_SETUP + r'''
import asyncio
from datetime import datetime, timezone
import httpx
from fastapi import FastAPI
from core import config
from core.dependencies import get_current_user
from database import get_db
from models import (
    CobrancaModel,
    ClienteModel,
    OrcamentoModel,
    PagamentoModel,
    PropostaModel,
    ProducaoModel,
    UsuarioModel,
)
from sqlalchemy import select
from routers.portal_cliente import get_mercado_pago_client as portal_provider
from routers.portal_cliente import router as portal_router
from services import financial_service as finance
from services import proposta_comercial_service as commercial

config.settings.COMMERCIAL_PIPELINE_V2_ENABLED = True

def accepted_for_client(db, budget_id, client, policy='entrada_50_50'):
    budget = db.get(OrcamentoModel, budget_id)
    budget.cliente_id = client.id
    db.commit()
    response = service.criar_por_orcamento(db, budget_id)
    proposal = db.get(PropostaModel, response.id)
    proposal.politica_pagamento = policy
    proposal.status = 'enviada'
    proposal.enviada_em = datetime.now(timezone.utc)
    budget.status = 'proposta_enviada'
    db.commit()
    db.expire_all()
    commercial.aprovar(db, proposal.id)
    return db.get(PropostaModel, proposal.id)

class StaticProviderSession(FakeSession):
    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        reference = kwargs['json']['external_reference']
        return FakeResponse(201, order(
            amount=kwargs['json']['total_amount'],
            status='processed', detail='accredited', method='pix', pix=True,
            provider_id='ORD-authenticated', external_reference=reference,
        ))
'''


class AuthenticatedCheckoutTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_policy_is_enforced_by_authenticated_routes_and_payment_releases_once(self):
        self.run_case(r'''
with Session(engine) as db:
    client_a = ClienteModel(nome='Cliente A', email='client-a@example.invalid', telefone='', observacoes='', ativo=True)
    client_b = ClienteModel(nome='Cliente B', email='client-b@example.invalid', telefone='', observacoes='', ativo=True)
    db.add_all([client_a, client_b])
    db.flush()
    integral = accepted_for_client(db, 1, client_a, 'integral')
    split = accepted_for_client(db, 2, client_b, 'entrada_50_50')
    user_a = UsuarioModel(username='client-a', password_hash='hash', role='cliente', is_admin=False, ativo=True, cliente_id=client_a.id)
    user_b = UsuarioModel(username='client-b', password_hash='hash', role='cliente', is_admin=False, ativo=True, cliente_id=client_b.id)
    db.add_all([user_a, user_b])
    db.commit()
    integral_id, split_id = integral.id, split.id
    client_a_id, client_b_id = client_a.id, client_b.id
    user_a_id, user_b_id = user_a.id, user_b.id

app = FastAPI()
app.include_router(portal_router)
def session():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = session
provider = MercadoPagoClient(access_token='synthetic-access-token', session=StaticProviderSession([]))
app.dependency_overrides[portal_provider] = lambda: provider
current = {'user': types.SimpleNamespace(id=user_a_id, role='cliente', is_admin=False, ativo=True, cliente_id=client_a_id)}
app.dependency_overrides[get_current_user] = lambda: current['user']

async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as http:
        summary = await http.get(f'/portal/cliente/propostas/{integral_id}/checkout')
        assert summary.status_code == 200, summary.text
        body = summary.json()
        assert body['politica_pagamento'] == 'integral'
        assert [item['tipo'] for item in body['opcoes']] == ['integral']
        forbidden = await http.post(f'/portal/cliente/propostas/{integral_id}/checkout/pix', json={'payment_option':'entrada'})
        assert forbidden.status_code == 409 and 'integral' in forbidden.json()['detail'].lower()
        with Session(engine) as check_db:
            assert check_db.query(PagamentoModel).count() == 0

        foreign = await http.get(f'/portal/cliente/propostas/{split_id}/checkout')
        assert foreign.status_code == 404
        foreign_payment = await http.post(
            f'/portal/cliente/propostas/{split_id}/checkout/pix',
            json={'payment_option': 'entrada'},
        )
        assert foreign_payment.status_code == 404

        current['user'] = types.SimpleNamespace(id=user_b_id, role='cliente', is_admin=False, ativo=True, cliente_id=client_b_id)
        split_summary = await http.get(f'/portal/cliente/propostas/{split_id}/checkout')
        assert split_summary.status_code == 200
        assert {item['tipo'] for item in split_summary.json()['opcoes']} == {'integral', 'entrada'}
        paid = await http.post(f'/portal/cliente/propostas/{split_id}/checkout/pix', json={'payment_option':'entrada'})
        assert paid.status_code == 200, paid.text
        assert paid.json()['status'] == 'approved'
        with Session(engine) as check_db:
            assert check_db.query(ProducaoModel).filter_by(orcamento_id=2).count() == 1
            charge = check_db.scalar(select(CobrancaModel).where(CobrancaModel.proposta_id == split_id))
            assert charge.status == 'parcialmente_paga'
            assert finance.saldo_pendente(charge) > 0
        again = await http.get(f'/portal/cliente/propostas/{split_id}/checkout')
        assert again.status_code == 200 and [item['tipo'] for item in again.json()['opcoes']] == ['saldo']
        assert (await http.get(f'/portal/cliente/propostas/{integral_id}/checkout')).status_code == 404

asyncio.run(check())
''')


if __name__ == '__main__':
    unittest.main()
