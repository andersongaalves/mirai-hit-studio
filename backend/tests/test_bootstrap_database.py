"""Disposable database tests; never load the project's .env settings."""

from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


class BootstrapTests(unittest.TestCase):
    def run_case(self, source):
        with tempfile.TemporaryDirectory(prefix="mirai-bootstrap-") as directory:
            url = "sqlite:///" + (Path(directory) / "test.db").as_posix()
            preamble = f"""
import sys, types
from unittest.mock import patch
config = types.ModuleType('core.config')
config.settings = types.SimpleNamespace(
    DATABASE_URL={url!r}, SECRET_KEY='test-only', ALGORITHM='HS256',
    API_NAME='Test', API_VERSION='1', DEBUG=False, HOST='localhost', PORT=8000,
    LOG_LEVEL='WARNING', ACCESS_TOKEN_EXPIRE_MINUTES=10, REFRESH_TOKEN_EXPIRE_DAYS=1,
    ALLOWED_ORIGINS='http://localhost', BACKUP_FOLDER={directory!r}, BACKUP_KEEP_DAYS=1,
    RESEND_API_KEY='test-only', EMAIL_FROM='test@example.invalid', ADMIN_EMAIL='test@example.invalid')
sys.modules['core.config'] = config
from sqlalchemy import inspect, event
from database import engine, Base
from scripts.bootstrap_database import bootstrap, BootstrapError, migration_config
def snapshot():
    with engine.connect() as connection:
        return connection.exec_driver_sql('SELECT type, name, sql FROM sqlite_master ORDER BY name').all()
def reject_ddl(connection, cursor, statement, parameters, context, many):
    assert statement.lstrip().split()[0].upper() not in {{'CREATE', 'ALTER', 'DROP'}}, statement
"""
            result = subprocess.run(
                [sys.executable, "-B", "-c", preamble + textwrap.dedent(source)],
                cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True,
                timeout=90,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_empty_head_upgrade_and_second_execution(self):
        self.run_case("""
            from alembic import command
            from alembic.script import ScriptDirectory
            from sqlalchemy.orm import configure_mappers
            head = bootstrap(engine)
            assert head == ScriptDirectory.from_config(migration_config()).get_current_head()
            assert set(inspect(engine).get_table_names()) == {
                'usuarios', 'servicos', 'clientes', 'orcamentos', 'propostas', 'producoes',
                'projetos', 'configuracoes', 'newsletter', 'alembic_version'}
            with engine.connect() as connection:
                assert connection.exec_driver_sql('SELECT version_num FROM alembic_version').all() == [(head,)]
            configure_mappers()
            from models import PropostaModel, OrcamentoModel
            assert PropostaModel.__table__ is Base.metadata.tables['propostas']
            assert OrcamentoModel.proposta.property.back_populates == 'orcamento'
            before = snapshot()
            from sqlalchemy.engine import Engine
            event.listen(Engine, 'before_cursor_execute', reject_ddl)
            command.upgrade(migration_config(), 'head')
            assert snapshot() == before
            with patch.object(Base.metadata, 'create_all', side_effect=AssertionError('create_all reached')):
                try:
                    bootstrap(engine)
                except BootstrapError as error:
                    assert 'database_not_empty' in str(error)
                else:
                    raise AssertionError('second bootstrap accepted')
            assert snapshot() == before
            with engine.connect() as connection:
                assert connection.exec_driver_sql('SELECT version_num FROM alembic_version').scalar_one() == head
        """)

    def test_partial_database_and_empty_version_table_refused(self):
        for ddl in (
            'CREATE TABLE servicos (id INTEGER PRIMARY KEY)',
            'CREATE TABLE alembic_version (version_num VARCHAR(32))',
            'CREATE VIEW example AS SELECT 1 AS id',
        ):
            with self.subTest(ddl=ddl):
                self.run_case(f"""
                    with engine.begin() as connection:
                        connection.exec_driver_sql({ddl!r})
                    before = snapshot()
                    event.listen(engine, 'before_cursor_execute', reject_ddl)
                    with patch.object(Base.metadata, 'create_all', side_effect=AssertionError('create_all reached')):
                        try:
                            bootstrap(engine)
                        except BootstrapError as error:
                            assert 'database_not_empty' in str(error)
                        else:
                            raise AssertionError('nonempty database accepted')
                    assert snapshot() == before
                    assert 'models' not in sys.modules
                """)

    def test_stamp_failure_rolls_back_without_cleanup(self):
        self.run_case("""
            from alembic.migration import MigrationContext
            statements = []
            event.listen(engine, 'before_cursor_execute',
                lambda connection, cursor, statement, parameters, context, many: statements.append(statement))
            with patch.object(MigrationContext, 'stamp', side_effect=RuntimeError('simulated failure')):
                try:
                    bootstrap(engine)
                except RuntimeError:
                    pass
                else:
                    raise AssertionError('failure hidden')
            assert snapshot() == []
            assert not any(s.lstrip().upper().startswith('DROP') for s in statements)
        """)

    def test_fastapi_import_and_startup_do_not_create_schema(self):
        self.run_case("""
            import asyncio
            bootstrap(engine)
            before = snapshot()
            async def check():
                with patch.object(Base.metadata, 'create_all', side_effect=AssertionError('automatic schema')), \\
                     patch('scripts.bootstrap_database.bootstrap', side_effect=AssertionError('automatic bootstrap')), \\
                     patch('socket.socket.connect', side_effect=AssertionError('network forbidden')):
                    event.listen(engine, 'before_cursor_execute', reject_ddl)
                    import main
                    with patch('services.startup_service.os.path.exists', return_value=False):
                        async with main.app.router.lifespan_context(main.app):
                            assert main.health() == {'status': 'healthy'}
            asyncio.run(check())
            assert snapshot() == before
        """)

    def test_cli_errors_hide_credentials(self):
        self.run_case("""
            import io
            from contextlib import redirect_stderr
            from scripts.bootstrap_database import main
            output = io.StringIO()
            with patch('scripts.bootstrap_database.bootstrap', side_effect=RuntimeError('credential-sentinel')):
                with redirect_stderr(output):
                    assert main() == 1
            assert 'bootstrap_failed' in output.getvalue()
            assert 'credential-sentinel' not in output.getvalue()
        """)

    def test_multiple_heads_refused_before_connection(self):
        self.run_case("""
            from alembic.script import ScriptDirectory
            with patch.object(ScriptDirectory, 'get_heads', return_value=['one', 'two']), \\
                 patch.object(engine, 'begin', side_effect=AssertionError('connection reached')):
                try:
                    bootstrap(engine)
                except BootstrapError as error:
                    assert 'invalid_heads' in str(error)
                else:
                    raise AssertionError('multiple heads accepted')
        """)


if __name__ == '__main__':
    unittest.main()
