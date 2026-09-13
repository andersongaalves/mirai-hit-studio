"""Focused dashboard contracts using only disposable SQLite data."""

import unittest

import test_bootstrap_database as isolated


SETUP = r'''
import asyncio
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import FastAPI
from sqlalchemy.orm import Session

from core.dependencies import get_current_user
from database import get_db
from models import ClienteModel, OrcamentoModel, ProducaoModel, PropostaModel
from routers.dashboard import router as dashboard_router

bootstrap(engine)
app = FastAPI()
app.include_router(dashboard_router)
def session():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = session
app.dependency_overrides[get_current_user] = lambda: object()
'''


class DashboardTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_dashboard_metrics_pipeline_and_activity(self):
        self.run_case(r'''
now = datetime.now(timezone.utc)
with Session(engine) as db:
    db.add_all([
        ClienteModel(nome='Ativo', email='ativo@example.com', ativo=True, created_at=now - timedelta(hours=1)),
        ClienteModel(nome='Inativo', email='inativo@example.com', ativo=False, created_at=now - timedelta(days=2)),
    ])
    db.flush()
    aberto = OrcamentoModel(nome_cliente='Lead', email='lead@example.com', servico='Mix', status='novo', data_solicitacao=now - timedelta(hours=2))
    analise = OrcamentoModel(nome_cliente='Lead 2', email='lead2@example.com', servico='Master', status='em_analise', data_solicitacao=now - timedelta(days=2))
    aprovado = OrcamentoModel(nome_cliente='Lead 3', email='lead3@example.com', servico='Beat', status='aprovado', data_solicitacao=now - timedelta(days=3))
    legado = OrcamentoModel(nome_cliente='Legado', email='legacy@example.com', servico='Voz', status='novo', cliente_id=None, data_solicitacao=now - timedelta(days=4))
    db.add_all([aberto, analise, aprovado, legado])
    db.flush()
    db.add_all([
        PropostaModel(orcamento_id=aberto.id, numero='P-ENVIADA', status='enviada', cliente_snapshot={}, itens_json=[], pagamentos_json=[], totais_json={}, enviada_em=now - timedelta(minutes=30)),
        PropostaModel(orcamento_id=aprovado.id, numero='P-ACEITA', status='aceita', cliente_snapshot={}, itens_json=[], pagamentos_json=[], totais_json={}, aprovada_em=now - timedelta(minutes=15)),
        ProducaoModel(titulo='Ativa', cliente='Cliente', servico='Mix', status='em_producao', etapas='[]', created_at=now - timedelta(minutes=20)),
        ProducaoModel(titulo='Atrasada', cliente='Cliente', servico='Master', status='revisao', etapas='[]', prazo_entrega=now - timedelta(days=1), created_at=now - timedelta(hours=3)),
        ProducaoModel(titulo='Finalizada', cliente='Cliente', servico='Beat', status='finalizado', etapas='[]', prazo_entrega=now - timedelta(days=1), created_at=now - timedelta(days=1)),
    ])
    db.commit()

async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get('/dashboard')
        assert response.status_code == 200, response.text
        data = response.json()
        assert data['metrics'] == {
            'clientes_ativos': 1,
            'orcamentos_abertos': 3,
            'propostas_aguardando_decisao': 1,
            'producoes_ativas': 2,
            'producoes_atrasadas': 1,
        }
        assert data['pipeline'] == {
            'orcamentos_abertos': 3,
            'propostas_enviadas': 1,
            'propostas_aprovadas': 1,
            'producoes_ativas': 2,
        }
        assert data['attention'] == {
            'producoes_atrasadas': 1,
            'propostas_aguardando_decisao': 1,
        }
        assert len(data['recent_activity']) <= 8
        assert data['recent_activity'] == sorted(data['recent_activity'], key=lambda item: item['data'], reverse=True)
        assert all('example.com' not in item['titulo'] for item in data['recent_activity'])
        assert any(item['tipo'] == 'proposta_aprovada' for item in data['recent_activity'])
asyncio.run(check())
''')

    def test_dashboard_empty_and_requires_authentication(self):
        self.run_case(r'''
async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get('/dashboard')
        assert response.status_code == 200
        data = response.json()
        assert all(value == 0 for value in data['metrics'].values())
        assert data['recent_activity'] == []
asyncio.run(check())
''')
        isolated.BootstrapTests().run_case(r'''
import asyncio
import httpx
from fastapi import FastAPI
from sqlalchemy.orm import Session
from database import get_db
from routers.dashboard import router
bootstrap(engine)
app = FastAPI()
app.include_router(router)
def session():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = session
async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        assert (await client.get('/dashboard')).status_code == 401
asyncio.run(check())
''')


if __name__ == "__main__":
    unittest.main()
