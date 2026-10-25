"""Focused dashboard contracts using only disposable SQLite data."""

import unittest

import test_bootstrap_database as isolated

SETUP = r'''
import asyncio
import types
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import FastAPI
from sqlalchemy.orm import Session

from core.dependencies import get_current_user
from database import get_db
from models import (
    AudioTagModel, BeatModel, ClienteModel, CobrancaModel, OrcamentoModel,
    PagamentoModel, PortfolioEnvioModel, PreviaTagJobModel, ProducaoArquivoModel,
    ProducaoEtapaModel, ProducaoModel, PropostaModel, UsuarioModel,
)
from routers.dashboard import router as dashboard_router

bootstrap(engine)
app = FastAPI()
app.include_router(dashboard_router)
def session():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = session
app.dependency_overrides[get_current_user] = lambda: types.SimpleNamespace(
    id=1, username='admin', role='admin', is_admin=True, ativo=True)
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
        PropostaModel(orcamento_id=analise.id, numero='P-VENCIDA', status='enviada', cliente_snapshot={}, itens_json=[], pagamentos_json=[], totais_json={}, enviada_em=now - timedelta(days=12)),
        PropostaModel(orcamento_id=aprovado.id, numero='P-ACEITA', status='aceita', cliente_snapshot={}, itens_json=[], pagamentos_json=[], totais_json={}, aprovada_em=now - timedelta(minutes=15)),
        ProducaoModel(titulo='Ativa', cliente='Cliente', servico='Mix', status='em_producao', etapas='[]', created_at=now - timedelta(minutes=20)),
        ProducaoModel(titulo='Atrasada', cliente='Cliente', servico='Master', status='revisao', etapas='[]', prazo_entrega=now - timedelta(days=1), created_at=now - timedelta(hours=3)),
        ProducaoModel(titulo='Finalizada', cliente='Cliente', servico='Beat', status='finalizado', etapas='[]', prazo_entrega=now - timedelta(days=1), created_at=now - timedelta(days=1)),
    ])
    produtor = UsuarioModel(username='produtor', password_hash='hash', role='produtor', is_admin=False, is_test=False)
    db.add(produtor)
    db.flush()
    tag = AudioTagModel(usuario_id=produtor.id, nome='tag.mp3', mime_type='audio/mpeg', conteudo=b'tag', sha256='a' * 64, duracao=1)
    db.add(tag)
    db.flush()
    beat = BeatModel(produtor_id=produtor.id, titulo='Beat', status='revisao', preco_lease=50, original_ref='beat/original', original_sha256='b' * 64, preview_ref='beat/preview', preview_sha256='c' * 64, tamanho_bytes=10, mime_type='audio/mpeg')
    envio = PortfolioEnvioModel(produtor_id=produtor.id, request_id='portfolio-request', dados={}, status='pendente', autorizado_em=now)
    db.add_all([beat, envio])
    db.flush()
    solicitacao = OrcamentoModel(nome_cliente='Cliente portal', email='portal@example.com', servico='Mix', status='novo', detalhes='Solicitacao pelo Portal do Cliente\nTitulo: Nova musica', is_test=False)
    db.add(solicitacao)
    db.flush()
    proposta_conciliacao = PropostaModel(orcamento_id=solicitacao.id, numero='P-CONCILIAR', status='aceita', cliente_snapshot={}, itens_json=[], pagamentos_json=[], totais_json={})
    db.add(proposta_conciliacao)
    db.flush()
    cobranca = CobrancaModel(proposta_id=proposta_conciliacao.id, valor_total=50, status='pendente', referencia_externa='dashboard-conciliacao')
    db.add(cobranca)
    db.flush()
    db.add(PagamentoModel(cobranca_id=cobranca.id, tipo='integral', valor=50, status='pendente', reconciliation_status='required'))
    producao_revisao = ProducaoModel(titulo='Entrega', cliente='Cliente', servico='Mix', status='revisao', etapas='[]')
    db.add(producao_revisao)
    db.flush()
    db.add(ProducaoEtapaModel(producao_id=producao_revisao.id, proposta_id=proposta_conciliacao.id, item_indice=1, item_descricao='Mix', ordem=1, ordem_no_item=1, nome='Entrega', peso_percentual=100, valor=50, unidade='faixa', status='em_revisao'))
    arquivo = ProducaoArquivoModel(producao_id=producao_revisao.id, remetente_usuario_id=produtor.id, tipo='previa', nome_exibicao='previa.mp3', mime_type='audio/mpeg', tamanho_bytes=10, sha256='d' * 64, object_key='dashboard/previa', visivel_produtor=True, original_restrito=True)
    db.add(arquivo)
    db.flush()
    db.add(PreviaTagJobModel(arquivo_id=arquivo.id, tag_id=tag.id, intervalo_segundos=10, volume_percentual=40, reserva_bytes=10, estado='erro'))
    db.commit()

async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get('/dashboard')
        assert response.status_code == 200, response.text
        data = response.json()
        assert data['metrics'] == {
            'clientes_ativos': 1,
            'orcamentos_abertos': 4,
            'propostas_aguardando_decisao': 1,
            'producoes_ativas': 3,
            'producoes_atrasadas': 1,
        }, data
        assert data['pipeline'] == {
            'orcamentos_abertos': 4,
            'propostas_enviadas': 2,
            'propostas_aprovadas': 2,
            'producoes_ativas': 3,
        }
        assert data['attention'] == {
            'producoes_atrasadas': 1,
            'propostas_aguardando_decisao': 1,
            'solicitacoes_producao': 1,
            'beats_em_revisao': 1,
            'portfolio_em_revisao': 1,
            'falhas_processamento_tag': 1,
            'pagamentos_em_conciliacao': 1,
            'entregas_aguardando_aprovacao': 1,
            'propostas_expiradas': 1,
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

    def test_operational_attention_excludes_test_chains(self):
        self.run_case(r'''
now = datetime.now(timezone.utc)
with Session(engine) as db:
    cliente = ClienteModel(nome='Teste', email='teste@example.com', ativo=True, is_test=True)
    produtor = UsuarioModel(username='produtor-teste', password_hash='hash', role='produtor', is_admin=False, is_test=True)
    db.add_all([cliente, produtor])
    db.flush()
    tag = AudioTagModel(usuario_id=produtor.id, nome='tag.mp3', mime_type='audio/mpeg', conteudo=b'tag', sha256='a' * 64, duracao=1)
    db.add(tag)
    db.flush()
    db.add_all([
        BeatModel(produtor_id=produtor.id, titulo='Beat teste', status='revisao', preco_lease=50, original_ref='teste/original', original_sha256='b' * 64, preview_ref='teste/preview', preview_sha256='c' * 64, tamanho_bytes=10, mime_type='audio/mpeg'),
        PortfolioEnvioModel(produtor_id=produtor.id, request_id='portfolio-test', dados={}, status='pendente', autorizado_em=now),
    ])
    orcamento = OrcamentoModel(nome_cliente=cliente.nome, email=cliente.email, cliente_id=cliente.id, servico='Mix', status='novo', detalhes='Solicitacao pelo Portal do Cliente\nTitulo: Teste', is_test=True)
    db.add(orcamento)
    db.flush()
    proposta = PropostaModel(orcamento_id=orcamento.id, numero='P-TESTE', status='aceita', cliente_snapshot={}, itens_json=[], pagamentos_json=[], totais_json={})
    db.add(proposta)
    db.flush()
    cobranca = CobrancaModel(proposta_id=proposta.id, cliente_id=cliente.id, valor_total=50, status='pendente', referencia_externa='dashboard-test')
    producao = ProducaoModel(titulo='Teste', cliente=cliente.nome, servico='Mix', status='revisao', etapas='[]', orcamento_id=orcamento.id)
    db.add_all([cobranca, producao])
    db.flush()
    db.add_all([
        PagamentoModel(cobranca_id=cobranca.id, tipo='integral', valor=50, status='pendente', reconciliation_status='required'),
        ProducaoEtapaModel(producao_id=producao.id, proposta_id=proposta.id, item_indice=1, item_descricao='Mix', ordem=1, ordem_no_item=1, nome='Entrega', peso_percentual=100, valor=50, unidade='faixa', status='em_revisao'),
    ])
    arquivo = ProducaoArquivoModel(producao_id=producao.id, remetente_usuario_id=produtor.id, tipo='previa', nome_exibicao='teste.mp3', mime_type='audio/mpeg', tamanho_bytes=10, sha256='d' * 64, object_key='dashboard/teste', visivel_produtor=True, original_restrito=True)
    db.add(arquivo)
    db.flush()
    db.add(PreviaTagJobModel(arquivo_id=arquivo.id, tag_id=tag.id, intervalo_segundos=10, volume_percentual=40, reserva_bytes=10, estado='erro'))
    db.commit()

async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        data = (await client.get('/dashboard')).json()
        assert all(value == 0 for value in data['attention'].values()), data
asyncio.run(check())
''')


if __name__ == "__main__":
    unittest.main()
