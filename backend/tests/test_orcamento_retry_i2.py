"""HTTP replay regression; disposable SQLite, no email transport."""
import unittest

import test_bootstrap_database as isolated


class OrcamentoRetryTests(unittest.TestCase):
    def test_migration_preserves_legacy_rows_and_unique_keys(self):
        isolated.BootstrapTests().run_case('''
            import importlib.util
            from pathlib import Path
            from alembic.migration import MigrationContext
            from alembic.operations import Operations
            from sqlalchemy.exc import IntegrityError
            path = Path('migrations/versions/b8c41e7d290a_orcamento_idempotency.py')
            spec = importlib.util.spec_from_file_location('i2_migration', path)
            revision = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(revision)
            with engine.begin() as connection:
                connection.exec_driver_sql('CREATE TABLE orcamentos (id INTEGER PRIMARY KEY)')
                connection.exec_driver_sql('INSERT INTO orcamentos (id) VALUES (1), (2)')
                with Operations.context(MigrationContext.configure(connection)):
                    revision.upgrade()
                assert connection.exec_driver_sql('SELECT id, idempotency_key, request_hash FROM orcamentos').all() == [(1,None,None),(2,None,None)]
                connection.exec_driver_sql("UPDATE orcamentos SET idempotency_key='test-key' WHERE id=1")
                try:
                    with connection.begin_nested():
                        connection.exec_driver_sql("UPDATE orcamentos SET idempotency_key='test-key' WHERE id=2")
                except IntegrityError:
                    pass
                else:
                    raise AssertionError('duplicate key accepted')
        ''')

    def test_identical_retry_reuses_budget_and_notifications(self):
        isolated.BootstrapTests().run_case('''
            from fastapi import FastAPI
            from uuid import uuid4
            from fastapi.testclient import TestClient
            from sqlalchemy.orm import Session
            from database import get_db
            from models import OrcamentoModel, ClienteModel
            from routers.orcamentos import router
            from services.email_service import EmailService
            bootstrap(engine)
            app = FastAPI()
            app.include_router(router)
            def session():
                with Session(engine) as db:
                    yield db
            app.dependency_overrides[get_db] = session
            payload = dict(nome_cliente='I2 Retry', email='i2-retry@example.com',
                           servico='Mixagem', valor_total=199.99, detalhes='Briefing I2')
            headers = {'Idempotency-Key': str(uuid4())}
            with TestClient(app) as http, patch.object(EmailService, 'enviar') as send:
                first = http.post('/orcamentos', json=payload, headers=headers)
                retry = http.post('/orcamentos', json=payload, headers=headers)
                assert first.status_code == retry.status_code == 200
                assert first.json()['id'] == retry.json()['id'], 'retry duplicated budget'
                assert send.call_count == 2, 'retry duplicated notifications'
                with Session(engine) as db:
                    assert db.query(OrcamentoModel).count() == 1
                    assert db.query(ClienteModel).count() == 1
                    saved = db.get(OrcamentoModel, first.json()['id'])
                    saved.observacoes = 'Private operator note'
                    db.commit()
                replay = http.post('/orcamentos', json=payload, headers=headers)
                assert 'Private operator note' not in replay.text
                conflict = http.post('/orcamentos', json={**payload, 'detalhes':'Other'}, headers=headers)
                assert conflict.status_code == 409
                assert http.post('/orcamentos', json=payload,
                                 headers={'Idempotency-Key':'invalid'}).status_code == 422
                separate = http.post('/orcamentos', json=payload,
                                     headers={'Idempotency-Key':str(uuid4())})
                assert separate.json()['id'] != first.json()['id']
                changed = http.post('/orcamentos', json={**payload, 'detalhes':'Different briefing'})
                assert changed.status_code == 200
                assert changed.json()['id'] != first.json()['id']
        ''')


if __name__ == '__main__':
    unittest.main()
