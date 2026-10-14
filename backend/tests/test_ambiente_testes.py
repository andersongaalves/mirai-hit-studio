"""Test-mode classification and backend filtering on an isolated database."""

import unittest

import test_bootstrap_database as isolated


SETUP = r"""
import asyncio
from decimal import Decimal
from types import SimpleNamespace

import httpx
from fastapi import FastAPI
from sqlalchemy.orm import Session

from core.dependencies import get_current_user
from database import get_db
from models import ClienteModel, OrcamentoModel, PropostaModel, ProducaoModel
from models.financeiro import CobrancaModel, PagamentoModel
from routers.dashboard import router as dashboard_router
from routers.financeiro import router as financeiro_router
from routers.orcamentos import router as budget_router
from routers.producao import router as production_router
from routers.clientes import router as client_router

bootstrap(engine)
app = FastAPI()
for r in (dashboard_router, financeiro_router, budget_router, production_router, client_router):
    app.include_router(r)
def session():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = session
app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
    id=1, username='admin', role='admin', is_admin=True, ativo=True)
"""


class AmbienteTestesTests(unittest.TestCase):
    def test_real_dashboard_and_finance_exclude_test_chains(self):
        isolated.BootstrapTests().run_case(SETUP + r"""
with Session(engine) as db:
    real = ClienteModel(nome='Real', email='real@example.com', ativo=True, is_test=False)
    test = ClienteModel(nome='Teste', email='teste@example.com', ativo=True, is_test=True)
    db.add_all([real, test])
    db.flush()
    for index, customer in enumerate((real, test)):
        budget = OrcamentoModel(nome_cliente=customer.nome, email=customer.email,
                                servico='Mix', cliente_id=customer.id, status='novo',
                                is_test=(index == 1))
        db.add(budget)
        db.flush()
        proposal = PropostaModel(orcamento_id=budget.id, numero='P-TEST-' + str(index),
                                 cliente_snapshot={}, itens_json=[], pagamentos_json=[],
                                 totais_json={}, status='aceita')
        db.add(proposal)
        db.flush()
        charge = CobrancaModel(proposta_id=proposal.id, cliente_id=customer.id,
                               valor_total=Decimal('50.00'), status='paga',
                               referencia_externa='ref-test-' + str(index))
        db.add(charge)
        db.flush()
        db.add(PagamentoModel(cobranca_id=charge.id, tipo='integral',
                            valor=Decimal('50.00'), status='aprovado'))
        db.add(ProducaoModel(titulo='Trabalho', cliente=customer.nome, servico='Mix',
                             status='em_producao', orcamento_id=budget.id, etapas='[]'))
    db.commit()

async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url='http://test') as client:
        dash = (await client.get('/dashboard')).json()
        assert dash['metrics']['clientes_ativos'] == 1, dash
        assert dash['metrics']['orcamentos_abertos'] == 1, dash
        assert dash['metrics']['producoes_ativas'] == 1, dash
        assert dash['pipeline']['propostas_aprovadas'] == 1, dash

        regular = (await client.get('/financeiro/resumo')).json()
        all_data = (await client.get('/financeiro/resumo?ambiente=todos')).json()
        tests = (await client.get('/financeiro/resumo?ambiente=teste')).json()
        assert regular['valor_recebido'] == '50.00', regular
        assert all_data['valor_recebido'] == '100.00', all_data
        assert tests['valor_recebido'] == '50.00', tests
        assert regular['total_cobrancas'] == 1
        assert all_data['total_cobrancas'] == 2
        assert (await client.get('/financeiro/cobrancas')).json()['total'] == 1
        assert (await client.get('/financeiro/cobrancas?ambiente=teste')).json()['total'] == 1
        assert len((await client.get('/clientes')).json()) == 1
        assert len((await client.get('/clientes?ambiente=teste')).json()) == 1
        assert len((await client.get('/orcamentos')).json()) == 1
        assert len((await client.get('/orcamentos?ambiente=teste')).json()) == 1
        assert len((await client.get('/producoes')).json()) == 1
        assert len((await client.get('/producoes?ambiente=teste')).json()) == 1
asyncio.run(check())
""")


if __name__ == "__main__":
    unittest.main()
