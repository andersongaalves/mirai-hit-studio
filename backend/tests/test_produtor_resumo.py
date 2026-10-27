"""AUD6-S09-002: producer page for the Admin — counts, order, test chains out, Admin only."""
import unittest

import test_bootstrap_database as isolated

CASE = r'''
import asyncio
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import FastAPI
from sqlalchemy.orm import Session

from core.security import create_access_token
from database import get_db
from models import BeatModel, OrcamentoModel, ProducaoModel, UsuarioModel
from routers.produtor_resumo import router

bootstrap(engine)
now = datetime.now(timezone.utc)
def beat(i, status):
    return BeatModel(produtor_id=2, titulo=f'Beat {i}', descricao='', generos='Trap', preco_lease=100,
        status=status, ativo=status == 'aprovado', original_ref=f'r2://temp/arquivos/{i:032x}/{i:032x}',
        original_sha256='a' * 64, preview_ref=f'r2://temp/arquivos/{i + 50:032x}/{i + 50:032x}',
        preview_sha256='b' * 64, tamanho_bytes=10, mime_type='audio/mpeg')
with Session(engine) as db:
    db.add_all([
        UsuarioModel(id=1, username='admin', password_hash='unused', role='admin', is_admin=True, ativo=True),
        UsuarioModel(id=2, username='ana.produtora', nome_exibicao='Ana Beats', password_hash='unused',
                     role='produtor', is_admin=False, ativo=True, painel_beats=True),
        UsuarioModel(id=3, username='cliente', password_hash='unused', role='produtor', is_admin=False, ativo=True),
        OrcamentoModel(id=9, nome_cliente='Teste', email='t@example.test', servico='Mix', valor_total=0, is_test=True),
    ])
    db.flush()
    db.add_all([
        ProducaoModel(id=1, titulo='Atrasada', cliente='Cliente A', servico='Mix', status='em_producao', etapas='[]',
                      produtor_id=2, prazo_entrega=now - timedelta(days=2)),
        ProducaoModel(id=2, titulo='No prazo', cliente='Cliente B', servico='Mix', status='revisao', etapas='[]',
                      produtor_id=2, prazo_entrega=now + timedelta(days=5)),
        ProducaoModel(id=3, titulo='Pronta', cliente='Cliente C', servico='Mix', status='finalizado', etapas='[]', produtor_id=2),
        ProducaoModel(id=4, titulo='Cadeia de teste', cliente='Teste', servico='Mix', status='em_producao', etapas='[]',
                      produtor_id=2, orcamento_id=9),
        beat(1, 'revisao'), beat(2, 'aprovado'), beat(3, 'aprovado'), beat(4, 'vendido'),
    ])
    db.commit()
app = FastAPI()
app.include_router(router)
def session():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = session
def bearer(name, uid):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': name, 'av': 0, 'uid': uid})}

async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        assert (await client.get('/admin/produtores/2/resumo')).status_code == 401
        assert (await client.get('/admin/produtores/2/resumo', headers=bearer('ana.produtora', 2))).status_code == 403
        assert (await client.get('/admin/produtores/1/resumo', headers=bearer('admin', 1))).status_code == 404
        data = (await client.get('/admin/produtores/2/resumo', headers=bearer('admin', 1))).json()
        assert data['produtor'] == {'id': 2, 'username': 'ana.produtora', 'nome_exibicao': 'Ana Beats', 'ativo': True, 'painel_beats': True, 'especialidades': []}
        assert data['contagens'] == {'producoes_ativas': 2, 'producoes_atrasadas': 1, 'producoes_finalizadas': 1,
                                     'beats_em_revisao': 1, 'beats_aprovados': 2, 'beats_vendidos': 1, 'beats_rejeitados': 0}
        assert [(p['id'], p['atrasada']) for p in data['producoes']] == [(2, False), (1, True), (3, False)]
asyncio.run(check())
'''


class ProdutorResumoTests(unittest.TestCase):
    def test_admin_producer_page(self):
        isolated.BootstrapTests().run_case(CASE)


if __name__ == "__main__":
    unittest.main()
