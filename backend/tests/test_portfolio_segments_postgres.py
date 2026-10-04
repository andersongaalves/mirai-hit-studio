"""Opt-in migration cycle for the segment catalog on disposable PostgreSQL 17."""

import json
import os
import unittest

from alembic import command
from scripts.bootstrap_database import migration_config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

DATABASE_URL = os.getenv("MIRAI_PORTALS_E2E_DATABASE_URL", "")
ACK = os.getenv("MIRAI_PORTALS_E2E_ALLOW", "")


@unittest.skipUnless(
    DATABASE_URL and ACK == "POSTGRES_17_DISPOSABLE_ONLY",
    "requires the disposable PostgreSQL 17 CI database",
)
class PortfolioSegmentsPostgreSQLTests(unittest.TestCase):
    def test_upgrade_downgrade_upgrade_backfill_and_jsonb(self):
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

        command.downgrade(config, "24ef7f883a03")
        try:
            with engine.begin() as connection:
                connection.execute(text("INSERT INTO configuracoes (id) VALUES (1)"))
                connection.execute(
                    text("""
                    INSERT INTO projetos
                        (id, titulo, artista, categoria, link_audio, link_capa, descricao,
                         destaque, segmentos_json, show_mix_comparison_on_landing)
                    VALUES
                        (900001, 'Legacy', 'Mirai', 'Mix', 'https://example.invalid/a.mp3',
                         'https://example.invalid/a.webp', 'Fixture', false,
                         CAST('["legacy_mix", "trap"]' AS JSON), false)
                """)
                )
            command.upgrade(config, "head")
            with engine.connect() as connection:
                self.assertEqual(
                    connection.execute(
                        text("""
                        SELECT data_type FROM information_schema.columns
                        WHERE table_name='configuracoes' AND column_name='portfolio_segments_json'
                    """)
                    ).scalar_one(),
                    "jsonb",
                )
                catalog = connection.execute(
                    text("SELECT portfolio_segments_json FROM configuracoes WHERE id=1")
                ).scalar_one()
                if isinstance(catalog, str):
                    catalog = json.loads(catalog)
                self.assertEqual(
                    [item["id"] for item in catalog], ["legacy_mix", "trap"]
                )

            command.downgrade(config, "24ef7f883a03")
            with engine.connect() as connection:
                self.assertEqual(
                    connection.execute(
                        text("SELECT segmentos_json FROM projetos WHERE id=900001")
                    ).scalar_one(),
                    ["legacy_mix", "trap"],
                )
            command.upgrade(config, "head")
        finally:
            command.upgrade(config, "head")
            with engine.begin() as connection:
                connection.execute(text("DELETE FROM projetos WHERE id=900001"))
                connection.execute(text("DELETE FROM configuracoes WHERE id=1"))

        self.assertIn(
            "portfolio_segments_json",
            {column["name"] for column in inspect(engine).get_columns("configuracoes")},
        )
        engine.dispose()
