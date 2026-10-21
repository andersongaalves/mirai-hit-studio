"""Exclusive and lease reservation race on disposable PostgreSQL 17."""

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

DATABASE_URL = os.getenv("MIRAI_PORTALS_E2E_DATABASE_URL", "")
ACK = os.getenv("MIRAI_PORTALS_E2E_ALLOW", "")
BASE_ID = 936100


@unittest.skipUnless(
    DATABASE_URL and ACK == "POSTGRES_17_DISPOSABLE_ONLY",
    "requires the disposable PostgreSQL 17 CI database",
)
class BeatCatalogPostgreSQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        url = make_url(DATABASE_URL)
        if url.host not in {"127.0.0.1", "localhost"}:
            raise RuntimeError("disposable localhost PostgreSQL required")
        if "portals_e2e" not in (url.database or ""):
            raise RuntimeError("disposable portals_e2e database required")
        cls.engine = create_engine(DATABASE_URL)
        with cls.engine.connect() as connection:
            major = (
                int(connection.execute(text("SHOW server_version_num")).scalar_one())
                // 10000
            )
            if major != 17:
                raise RuntimeError("PostgreSQL 17 required")

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def tearDown(self):
        with self.engine.begin() as connection:
            connection.execute(
                text("DELETE FROM beat_licencas WHERE beat_id=:id"), {"id": BASE_ID}
            )
            connection.execute(
                text("DELETE FROM propostas WHERE id IN (:first, :second)"),
                {"first": BASE_ID, "second": BASE_ID + 1},
            )
            connection.execute(
                text("DELETE FROM orcamentos WHERE id IN (:first, :second)"),
                {"first": BASE_ID, "second": BASE_ID + 1},
            )
            connection.execute(text("DELETE FROM beats WHERE id=:id"), {"id": BASE_ID})
            connection.execute(
                text("DELETE FROM clientes WHERE id IN (:first, :second)"),
                {"first": BASE_ID, "second": BASE_ID + 1},
            )
            connection.execute(
                text("DELETE FROM usuarios WHERE id=:id"), {"id": BASE_ID}
            )

    def test_exclusive_and_lease_cannot_be_reserved_concurrently(self):
        from models import (
            BeatLicencaModel,
            BeatModel,
            ClienteModel,
            OrcamentoModel,
            PropostaModel,
            UsuarioModel,
        )
        from services import beat_service

        with Session(self.engine) as db:
            producer = UsuarioModel(
                id=BASE_ID,
                username="beat-race-producer",
                password_hash="unused",
                role="produtor",
                is_admin=False,
                ativo=True,
                painel_beats=True,
            )
            clients = [
                ClienteModel(
                    id=BASE_ID, nome="Beat race A", email="beat-a@example.invalid"
                ),
                ClienteModel(
                    id=BASE_ID + 1, nome="Beat race B", email="beat-b@example.invalid"
                ),
            ]
            budgets = [
                OrcamentoModel(
                    id=BASE_ID,
                    nome_cliente="Beat race A",
                    email="beat-a@example.invalid",
                    servico="Beat",
                    valor_total=500,
                    status="aprovado",
                ),
                OrcamentoModel(
                    id=BASE_ID + 1,
                    nome_cliente="Beat race B",
                    email="beat-b@example.invalid",
                    servico="Beat",
                    valor_total=100,
                    status="aprovado",
                ),
            ]
            beat = BeatModel(
                id=BASE_ID,
                produtor_id=BASE_ID,
                titulo="Race",
                descricao="",
                generos="",
                preco_lease=Decimal("100.00"),
                preco_exclusivo=Decimal("500.00"),
                status="aprovado",
                ativo=True,
                original_ref="r2://temp/arquivos/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                original_sha256="a" * 64,
                preview_ref="r2://temp/arquivos/cccccccccccccccccccccccccccccccc/dddddddddddddddddddddddddddddddd",
                preview_sha256="b" * 64,
                tamanho_bytes=10,
                mime_type="audio/mpeg",
            )
            proposals = [
                PropostaModel(
                    id=BASE_ID,
                    orcamento_id=BASE_ID,
                    numero="BEAT-RACE-EXCLUSIVE",
                    status="aceita",
                    cliente_snapshot={},
                    itens_json=[
                        {
                            "beat_id": BASE_ID,
                            "licenca_beat": "exclusivo",
                            "valor_unitario": "500.00",
                        }
                    ],
                ),
                PropostaModel(
                    id=BASE_ID + 1,
                    orcamento_id=BASE_ID + 1,
                    numero="BEAT-RACE-LEASE",
                    status="aceita",
                    cliente_snapshot={},
                    itens_json=[
                        {
                            "beat_id": BASE_ID,
                            "licenca_beat": "lease",
                            "valor_unitario": "100.00",
                        }
                    ],
                ),
            ]
            db.add(producer)
            db.add_all(clients + budgets + [beat] + proposals)
            db.commit()

        def reserve(proposal_id, client_id):
            with Session(self.engine) as db:
                proposal = db.get(PropostaModel, proposal_id)
                try:
                    beat_service.reserve_for_proposal(db, proposal, client_id)
                    db.commit()
                    return "reserved"
                except Exception as error:
                    db.rollback()
                    return getattr(error, "status_code", None)

        with ThreadPoolExecutor(max_workers=2) as pool:
            exclusive = pool.submit(reserve, BASE_ID, BASE_ID)
            lease = pool.submit(reserve, BASE_ID + 1, BASE_ID + 1)
            outcomes = sorted(
                [
                    exclusive.result(),
                    lease.result(),
                ],
                key=str,
            )

        self.assertEqual(outcomes.count("reserved"), 1)
        self.assertEqual(outcomes.count(409), 1)
        with Session(self.engine) as db:
            licenses = db.scalars(
                select(BeatLicencaModel).where(BeatLicencaModel.beat_id == BASE_ID)
            ).all()
            self.assertEqual(len(licenses), 1)
            self.assertEqual(licenses[0].status, "reservada")


if __name__ == "__main__":
    unittest.main()
