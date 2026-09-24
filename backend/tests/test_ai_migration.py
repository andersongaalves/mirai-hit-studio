"""Only a disposable database; historical migrations and real databases are untouched."""

import unittest

import test_bootstrap_database as isolated


class AIMigrationTests(unittest.TestCase):
    def test_postgresql_ddl_is_private_and_compiles_without_connection(self):
        isolated.BootstrapTests().run_case(r'''
import importlib.util
import io
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_mock_engine
import models

buffer = io.StringIO()
context = MigrationContext.configure(dialect_name='postgresql', opts={'as_sql': True, 'output_buffer': buffer})
spec = importlib.util.spec_from_file_location('ai_revision', 'migrations/versions/c8a1d6e4b209_create_ai_core.py')
revision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(revision)
with Operations.context(context):
    revision.upgrade()
sql = buffer.getvalue()
for table in ['ai_conversations', 'ai_messages']:
    assert 'CREATE TABLE ' + table in sql
    assert 'ALTER TABLE ' + table + ' ENABLE ROW LEVEL SECURITY' in sql
    assert 'REVOKE ALL ON TABLE ' + table + ' FROM anon' in sql
    assert 'REVOKE ALL ON TABLE ' + table + ' FROM authenticated' in sql
    assert 'DROP TABLE' not in sql
briefing_spec = importlib.util.spec_from_file_location('briefing_revision', 'migrations/versions/e8b2c6d4f701_create_ai_briefings.py')
briefing_revision = importlib.util.module_from_spec(briefing_spec)
briefing_spec.loader.exec_module(briefing_revision)
buffer = io.StringIO()
context = MigrationContext.configure(dialect_name='postgresql', opts={'as_sql': True, 'output_buffer': buffer})
with Operations.context(context):
    briefing_revision.upgrade()
assert 'ALTER TABLE ai_briefings ENABLE ROW LEVEL SECURITY' in buffer.getvalue()
assert 'REVOKE ALL ON TABLE ai_briefings FROM anon' in buffer.getvalue()
assert 'REVOKE ALL ON TABLE ai_briefings FROM authenticated' in buffer.getvalue()
emitted = []
mock = create_mock_engine('postgresql://', lambda statement, *args, **kwargs: emitted.append(str(statement.compile(dialect=mock.dialect))))
Base.metadata.create_all(mock, tables=[Base.metadata.tables['ai_conversations'], Base.metadata.tables['ai_messages']])
for table in ['ai_conversations', 'ai_messages']:
    assert any('ALTER TABLE ' + table + ' ENABLE ROW LEVEL SECURITY' in ddl for ddl in emitted)
''')

    def test_upgrade_downgrade_upgrade_and_metadata(self):
        isolated.BootstrapTests().run_case(r'''
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.orm import configure_mappers
import models

ai_tables = {'ai_conversations', 'ai_messages', 'ai_email_threads', 'ai_briefings'}
# Historical chain starts from a preexisting schema. Build the parent schema only
# in this disposable database, then exercise the new revision through Alembic.
with engine.begin() as connection:
    Base.metadata.create_all(connection, tables=[table for table in Base.metadata.sorted_tables
                                                if table.name not in ai_tables])
command.stamp(migration_config(), 'f6c2a8d4e1b9')
assert ScriptDirectory.from_config(migration_config()).get_heads() == ['e8b2c6d4f701']
command.upgrade(migration_config(), 'head')
assert ai_tables <= set(inspect(engine).get_table_names())
with engine.connect() as connection:
    differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert not differences, differences
    assert connection.exec_driver_sql('SELECT version_num FROM alembic_version').scalar_one() == 'e8b2c6d4f701'
configure_mappers()
command.downgrade(migration_config(), 'f6c2a8d4e1b9')
assert not ai_tables & set(inspect(engine).get_table_names())
assert 'clientes' in inspect(engine).get_table_names()
command.upgrade(migration_config(), 'head')
with engine.connect() as connection:
    assert not compare_metadata(MigrationContext.configure(connection), Base.metadata)
''')


if __name__ == "__main__":
    unittest.main()
