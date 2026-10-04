"""Opt-in migration cycle for client access on disposable PostgreSQL 17."""

import os
import unittest
from concurrent.futures import ThreadPoolExecutor

from alembic import command
from scripts.bootstrap_database import migration_config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

DATABASE_URL = os.getenv("MIRAI_PORTALS_E2E_DATABASE_URL", "")
ACK = os.getenv("MIRAI_PORTALS_E2E_ALLOW", "")
PREVIOUS_REVISION = "5b7c9d1e4f62"
HEAD_REVISION = "a41b7d8de6d7"


@unittest.skipUnless(
    DATABASE_URL and ACK == "POSTGRES_17_DISPOSABLE_ONLY",
    "requires the disposable PostgreSQL 17 CI database",
)
class ClientAccessMigrationPostgreSQLTests(unittest.TestCase):
    def test_upgrade_downgrade_upgrade_constraints_and_concurrency(self):
        url = make_url(DATABASE_URL)
        self.assertIn(url.host, {"127.0.0.1", "localhost"})
        self.assertIn("portals_e2e", url.database or "")
        engine = create_engine(DATABASE_URL)
        config = migration_config()

        with engine.connect() as connection:
            self.assertEqual(
                int(connection.execute(text("SHOW server_version_num")).scalar_one())
                // 10000,
                17,
            )

        if inspect(engine).has_table("cliente_acessos"):
            command.downgrade(config, PREVIOUS_REVISION)
        else:
            # Bootstrap uses current model metadata and stamps the current head.
            command.stamp(config, PREVIOUS_REVISION)

        try:
            self._insert_existing_rows(engine)
            command.upgrade(config, "head")
            self._assert_schema_security(engine)
            self._assert_constraints(engine)
            self._assert_atomic_rate_limit(engine)
            self._assert_transaction_rollback(engine)

            command.downgrade(config, PREVIOUS_REVISION)
            inspector = inspect(engine)
            self.assertFalse(inspector.has_table("cliente_acessos"))
            self.assertFalse(inspector.has_table("auth_rate_limits"))
            with engine.connect() as connection:
                self.assertEqual(
                    connection.execute(
                        text("SELECT count(*) FROM clientes WHERE id IN (910001, 910002)")
                    ).scalar_one(),
                    2,
                )
                self.assertEqual(
                    connection.execute(
                        text("SELECT count(*) FROM usuarios WHERE id = 910001")
                    ).scalar_one(),
                    1,
                )

            command.upgrade(config, "head")
            with engine.connect() as connection:
                self.assertEqual(
                    connection.execute(
                        text("SELECT version_num FROM alembic_version")
                    ).scalar_one(),
                    HEAD_REVISION,
                )
        finally:
            command.upgrade(config, "head")
            with engine.begin() as connection:
                connection.execute(text("DELETE FROM cliente_acessos"))
                connection.execute(text("DELETE FROM auth_rate_limits"))
                connection.execute(text("DELETE FROM usuarios WHERE id = 910001"))
                connection.execute(
                    text("DELETE FROM clientes WHERE id IN (910001, 910002)")
                )
            engine.dispose()

    @staticmethod
    def _insert_existing_rows(engine):
        with engine.begin() as connection:
            connection.execute(
                text("""
                    INSERT INTO clientes
                        (id, nome, email, telefone, observacoes, ativo)
                    VALUES
                        (910001, 'Cliente Migration A', 'a@example.invalid', NULL, '', true),
                        (910002, 'Cliente Migration B', 'b@example.invalid', NULL, '', true)
                """)
            )
            connection.execute(
                text("""
                    INSERT INTO usuarios
                        (id, username, password_hash, is_admin, ativo, role, cliente_id)
                    VALUES
                        (910001, 'migration_admin', 'synthetic-hash', true, true,
                         'admin', NULL)
                """)
            )

    def _assert_schema_security(self, engine):
        inspector = inspect(engine)
        self.assertTrue(inspector.has_table("cliente_acessos"))
        self.assertTrue(inspector.has_table("auth_rate_limits"))
        with engine.connect() as connection:
            rls = dict(
                connection.execute(
                    text("""
                        SELECT relname, relrowsecurity
                        FROM pg_class
                        WHERE relname IN ('cliente_acessos', 'auth_rate_limits')
                    """)
                ).all()
            )
            self.assertEqual(
                rls,
                {"cliente_acessos": True, "auth_rate_limits": True},
            )
            for role in ("anon", "authenticated"):
                for table in ("cliente_acessos", "auth_rate_limits"):
                    self.assertFalse(
                        connection.execute(
                            text("SELECT has_table_privilege(:role, :table, 'SELECT')"),
                            {"role": role, "table": table},
                        ).scalar_one()
                    )
                self.assertFalse(
                    connection.execute(
                        text("""
                            SELECT has_sequence_privilege(
                                :role, 'cliente_acessos_id_seq', 'USAGE'
                            )
                        """),
                        {"role": role},
                    ).scalar_one()
                )

    def _assert_constraints(self, engine):
        token_hash = "a" * 64
        with engine.begin() as connection:
            connection.execute(
                text("""
                    INSERT INTO cliente_acessos (
                        cliente_id, email_normalizado, origem, token_finalidade,
                        token_hash, token_expires_at, invited_by_user_id
                    ) VALUES (
                        910001, 'a@example.invalid', 'admin_invite', 'convite',
                        :token_hash, now() + interval '1 hour', 910001
                    )
                """),
                {"token_hash": token_hash},
            )

        with self.assertRaises(IntegrityError), engine.begin() as connection:
            connection.execute(
                text("""
                        INSERT INTO cliente_acessos (
                            cliente_id, email_normalizado, origem, token_finalidade,
                            token_hash, token_expires_at, invited_by_user_id
                        ) VALUES (
                            910002, 'a@example.invalid', 'admin_invite', 'convite',
                            :token_hash, now() + interval '1 hour', 910001
                        )
                    """),
                {"token_hash": "b" * 64},
            )

        with self.assertRaises(IntegrityError), engine.begin() as connection:
            connection.execute(
                text("""
                        INSERT INTO cliente_acessos (
                            cliente_id, email_normalizado, origem, token_hash,
                            token_expires_at, privacy_accepted_at
                        ) VALUES (
                            910002, 'b@example.invalid', 'public_signup', :token_hash,
                            now() + interval '1 hour', now()
                        )
                    """),
                {"token_hash": "c" * 64},
            )

    @staticmethod
    def _assert_atomic_rate_limit(engine):
        key_hash = "d" * 64

        def increment(_):
            with engine.begin() as connection:
                return connection.execute(
                    text("""
                        INSERT INTO auth_rate_limits (
                            key_hash, action, window_started_at, request_count,
                            expires_at
                        ) VALUES (
                            :key_hash, 'activation', now(), 1,
                            now() + interval '1 hour'
                        )
                        ON CONFLICT (key_hash) DO UPDATE
                        SET request_count = auth_rate_limits.request_count + 1,
                            updated_at = now()
                        RETURNING request_count
                    """),
                    {"key_hash": key_hash},
                ).scalar_one()

        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(increment, range(8)))

        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT request_count FROM auth_rate_limits WHERE key_hash=:key"),
                {"key": key_hash},
            ).scalar_one() == 8

    def _assert_transaction_rollback(self, engine):
        key_hash = "e" * 64
        with self.assertRaises(RuntimeError), engine.begin() as connection:
            connection.execute(
                text("""
                        INSERT INTO auth_rate_limits (
                            key_hash, action, window_started_at, request_count,
                            expires_at
                        ) VALUES (
                            :key_hash, 'signup', now(), 1,
                            now() + interval '1 hour'
                        )
                    """),
                {"key_hash": key_hash},
            )
            raise RuntimeError("force rollback")
        with engine.connect() as connection:
            self.assertEqual(
                connection.execute(
                    text("SELECT count(*) FROM auth_rate_limits WHERE key_hash=:key"),
                    {"key": key_hash},
                ).scalar_one(),
                0,
            )
