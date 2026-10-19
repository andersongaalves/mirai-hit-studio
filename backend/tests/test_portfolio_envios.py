"""Private submissions, consent, publication and replay at the real API boundary."""

import textwrap
import unittest

import test_bootstrap_database as isolated
from test_portfolio_creditos import SETUP


class PortfolioEnviosTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + textwrap.dedent(source))

    def test_private_submission_review_and_replay(self):
        self.run_case('''
            from uuid import uuid4
            from models import ClienteModel, PortfolioEnvioModel
            producer = {'Authorization': 'Bearer ' + create_access_token({'sub': 'beatmaker', 'av': 0})}
            with Session(engine) as db:
                db.add(ClienteModel(id=1, nome='Synthetic', email='synthetic@example.test'))
                db.flush()
                db.add(UsuarioModel(id=4, username='other', password_hash='unused', role='produtor', is_admin=False, ativo=True))
                db.add(UsuarioModel(id=5, username='client', password_hash='unused', role='cliente', is_admin=False, ativo=True, cliente_id=1))
                db.commit()
            other = {'Authorization': 'Bearer ' + create_access_token({'sub': 'other', 'av': 0})}
            client_headers = {'Authorization': 'Bearer ' + create_access_token({'sub': 'client', 'av': 0})}
            data = {k:v for k,v in PAYLOAD.items() if k not in ('segmentos_json', 'destaque')}
            data.update(request_id=str(uuid4()), autorizacao_artista=True, funcao='mixagem')
            async def check():
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://test') as client:
                    path = '/portal/produtor/portfolio'
                    assert (await client.post(path, json=data)).status_code == 401
                    assert (await client.post(path, json=data, headers=client_headers)).status_code == 403
                    for invalid in (False, 1, 'true', None):
                        bad = await client.post(path, json={**data, 'autorizacao_artista': invalid}, headers=producer)
                        assert bad.status_code == 422, bad.text
                    for bad in ({'producao_id':999}, {'link_audio':''}, {'funcao':'outra'}, {'destaque':True}):
                        result = await client.post(path, json={**data, **bad}, headers=producer)
                        assert result.status_code in (404, 422), result.text
                    created = await client.post(path, json=data, headers=producer)
                    assert created.status_code == 201, created.text
                    item = created.json()
                    assert item['status'] == 'pendente' and item['projeto_id'] is None
                    assert (await client.get('/projetos')).json() == []
                    assert (await client.get('/projetos/public/mix-comparisons')).json() == []
                    assert (await client.get(path, headers=other)).json() == []
                    assert (await client.get('/projetos/envios/admin', headers=producer)).status_code == 403
                    replay = await client.post(path, json=data, headers=producer)
                    assert replay.json()['id'] == item['id']
                    conflict = await client.post(path, json={**data, 'titulo':'Outro titulo'}, headers=producer)
                    assert conflict.status_code == 409
                    review = f"/projetos/envios/{item['id']}/revisao"
                    decision = {'versao':1, 'decisao':'aprovar'}
                    assert (await client.post(review, json=decision, headers=producer)).status_code == 403
                    assert (await client.post(review, json={**decision,'versao':2}, headers=headers)).status_code == 409
                    approved = await client.post(review, json=decision, headers=headers)
                    assert approved.status_code == 200, approved.text
                    public = (await client.get('/projetos')).json()
                    assert len(public) == 1 and public[0]['titulo'] == data['titulo']
                    assert public[0]['creditos'] == [{'funcao':'mixagem','funcao_outra':None,'nome':'beatmaker'}]
                    assert 'produtor_id' not in public[0] and 'autorizado_em' not in public[0]
                    repeated = await client.post(review, json=decision, headers=headers)
                    assert repeated.json()['projeto_id'] == approved.json()['projeto_id']
                    assert (await client.post(review, json={'versao':2,'decisao':'recusar','motivo':'Outro motivo'}, headers=headers)).status_code == 409
                    second = await client.post(path, json={**data,'request_id':str(uuid4())}, headers=producer)
                    review2 = f"/projetos/envios/{second.json()['id']}/revisao"
                    assert (await client.post(review2, json={'versao':1,'decisao':'recusar'}, headers=headers)).status_code == 422
                    rejected = await client.post(review2, json={'versao':1,'decisao':'recusar','motivo':'Sem material publicado'}, headers=headers)
                    assert rejected.json()['status'] == 'recusado'
                    assert len((await client.get('/projetos')).json()) == 1
                    third = await client.post(path, json={**data,'request_id':str(uuid4())}, headers=producer)
                    with Session(engine) as db:
                        db.get(UsuarioModel, 2).ativo = False
                        db.commit()
                    blocked = await client.post(f"/projetos/envios/{third.json()['id']}/revisao", json=decision, headers=headers)
                    assert blocked.status_code == 409, blocked.text
                    with Session(engine) as db:
                        assert db.query(ProjetoModel).count() == 1
                        assert db.query(PortfolioEnvioModel).count() == 3
            asyncio.run(check())
        ''')

    def test_migration_roundtrip_and_private_bootstrap(self):
        isolated.BootstrapTests().run_case('''
from alembic import command
from sqlalchemy import create_mock_engine, inspect
from database import Base
from models import PortfolioEnvioModel
assert bootstrap(engine) == 'a1c3e5f7b902'
assert 'portfolio_envios' in inspect(engine).get_table_names()
command.downgrade(migration_config(), 'b4d6f8a0c357')
assert 'portfolio_envios' not in inspect(engine).get_table_names()
command.upgrade(migration_config(), 'head')
assert 'portfolio_envios' in inspect(engine).get_table_names()
ddl = []
mock = create_mock_engine('postgresql://', lambda sql, *a, **kw: ddl.append(str(sql.compile(dialect=mock.dialect))))
PortfolioEnvioModel.__table__.create(mock)
assert any('ENABLE ROW LEVEL SECURITY' in sql for sql in ddl)
for role in ('anon', 'authenticated'):
    assert any('FROM ' + role in sql and 'REVOKE ALL ON TABLE' in sql and 'REVOKE ALL ON SEQUENCE' in sql for sql in ddl)
''')


if __name__ == "__main__":
    unittest.main()
