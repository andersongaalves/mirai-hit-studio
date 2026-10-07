"""Opt-in migration and concurrency checks on disposable PostgreSQL 17."""

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal

from alembic import command
from scripts.bootstrap_database import migration_config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

DATABASE_URL = os.getenv("MIRAI_PORTALS_E2E_DATABASE_URL", "")
ACK = os.getenv("MIRAI_PORTALS_E2E_ALLOW", "")
PREVIOUS_REVISION = "b3e6f9a2c741"
HEAD_REVISION = "c5f2a7d9e184"
IDS = (935001, 935002)


@unittest.skipUnless(
    DATABASE_URL and ACK == "POSTGRES_17_DISPOSABLE_ONLY",
    "requires the disposable PostgreSQL 17 CI database",
)
class CommercePolicyPostgreSQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        url = make_url(DATABASE_URL)
        if url.host not in {"127.0.0.1", "localhost"}:
            raise RuntimeError("disposable localhost PostgreSQL required")
        if "portals_e2e" not in (url.database or ""):
            raise RuntimeError("disposable portals_e2e database required")
        cls.engine = create_engine(DATABASE_URL)
        with cls.engine.connect() as connection:
            major = int(
                connection.execute(text("SHOW server_version_num")).scalar_one()
            ) // 10000
            if major != 17:
                raise RuntimeError("PostgreSQL 17 required")

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def tearDown(self):
        command.upgrade(migration_config(), "head")
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "DELETE FROM audit_logs "
                    "WHERE action='production.released_by_payment' "
                    "AND (metadata_json->>'proposal_id')::int = ANY(:ids)"
                ),
                {"ids": list(IDS)},
            )
            connection.execute(
                text("DELETE FROM producoes WHERE orcamento_id = ANY(:ids)"),
                {"ids": list(IDS)},
            )
            connection.execute(
                text(
                    "DELETE FROM pagamentos WHERE cobranca_id IN "
                    "(SELECT id FROM cobrancas WHERE proposta_id = ANY(:ids))"
                ),
                {"ids": list(IDS)},
            )
            connection.execute(
                text("DELETE FROM cobrancas WHERE proposta_id = ANY(:ids)"),
                {"ids": list(IDS)},
            )
            connection.execute(
                text("DELETE FROM propostas WHERE id = ANY(:ids)"),
                {"ids": list(IDS)},
            )
            connection.execute(
                text("DELETE FROM orcamentos WHERE id = ANY(:ids)"),
                {"ids": list(IDS)},
            )

    def test_upgrade_downgrade_upgrade_backfill_and_constraints(self):
        config = migration_config()
        if "politica_pagamento" in {
            column["name"]
            for column in inspect(self.engine).get_columns("propostas")
        }:
            command.downgrade(config, PREVIOUS_REVISION)
        else:
            command.stamp(config, PREVIOUS_REVISION)

        with self.engine.begin() as connection:
            self._insert_legacy_fixture(connection, 935001, "aceita")
            self._insert_legacy_fixture(connection, 935002, "enviada")
            connection.execute(
                text(
                    """INSERT INTO producoes
                       (titulo, cliente, servico, status, orcamento_id, observacoes, etapas)
                       VALUES ('Fixture', 'Synthetic', 'Mix', 'aguardando_inicio',
                               935001, '', '[]')"""
                )
            )
            charge_id = connection.execute(
                text(
                    """INSERT INTO cobrancas
                       (proposta_id, valor_total, moeda, status, referencia_externa)
                       VALUES (935001, 199.99, 'BRL', 'parcialmente_paga',
                               '00000000-0000-0000-0000-000000935001')
                       RETURNING id"""
                )
            ).scalar_one()
            connection.execute(
                text(
                    """INSERT INTO pagamentos
                       (cobranca_id, tipo, valor, status)
                       VALUES (:charge, 'entrada', 99.99, 'aprovado')"""
                ),
                {"charge": charge_id},
            )

        command.upgrade(config, "head")
        inspector = inspect(self.engine)
        policy = next(
            item
            for item in inspector.get_columns("propostas")
            if item["name"] == "politica_pagamento"
        )
        self.assertFalse(policy["nullable"])
        self.assertIn("entrada_50_50", str(policy["default"]))
        checks = {
            item["name"] for item in inspector.get_check_constraints("propostas")
        }
        self.assertIn("ck_propostas_politica_pagamento_valida", checks)
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT id, politica_pagamento, status FROM propostas "
                    "WHERE id = ANY(:ids) ORDER BY id"
                ),
                {"ids": list(IDS)},
            ).all()
            self.assertEqual(
                rows,
                [
                    (935001, "entrada_50_50", "aceita"),
                    (935002, "entrada_50_50", "enviada"),
                ],
            )
            self.assertEqual(
                connection.execute(
                    text("SELECT count(*) FROM producoes WHERE orcamento_id=935001")
                ).scalar_one(),
                1,
            )
        with self.assertRaises(IntegrityError), self.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE propostas SET politica_pagamento='manual' WHERE id=935001"
                )
            )
        with self.assertRaises(IntegrityError), self.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE propostas SET politica_pagamento=NULL WHERE id=935001"
                )
            )

        command.downgrade(config, PREVIOUS_REVISION)
        self.assertNotIn(
            "politica_pagamento",
            {
                column["name"]
                for column in inspect(self.engine).get_columns("propostas")
            },
        )
        command.upgrade(config, "head")
        with self.engine.connect() as connection:
            self.assertEqual(
                connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one(),
                HEAD_REVISION,
            )

    def test_concurrent_release_creates_one_production(self):
        from models import CobrancaModel, OrcamentoModel, PagamentoModel, PropostaModel
        from services import producao_liberacao_service as release

        with Session(self.engine) as db:
            budget = OrcamentoModel(
                id=935001,
                nome_cliente="Synthetic",
                email="synthetic@example.invalid",
                servico="Mix",
                valor_total=Decimal("199.99"),
                status="aprovado",
                observacoes="",
            )
            proposal = PropostaModel(
                id=935001,
                orcamento_id=budget.id,
                numero="PG-935001",
                status="aceita",
                politica_pagamento="entrada_50_50",
                cliente_snapshot={
                    "cliente": {
                        "nome": "Synthetic",
                        "email": "synthetic@example.invalid",
                    },
                    "orcamento": {"id": budget.id, "servico": "Mix"},
                },
                objeto="Mix",
                descricao="Synthetic",
                itens_json=[
                    {
                        "descricao": "Mix",
                        "quantidade": "1",
                        "valor_unitario": "199.99",
                        "desconto": "0",
                    }
                ],
                pagamentos_json=[],
                condicoes="Synthetic",
                totais_json={
                    "subtotal": "199.99",
                    "desconto": "0.00",
                    "total": "199.99",
                },
            )
            charge = CobrancaModel(
                proposta=proposal,
                valor_total=Decimal("199.99"),
                moeda="BRL",
                status="parcialmente_paga",
            )
            db.add_all(
                [
                    budget,
                    proposal,
                    charge,
                    PagamentoModel(
                        cobranca=charge,
                        tipo="entrada",
                        valor=Decimal("99.99"),
                        status="aprovado",
                    ),
                ]
            )
            db.commit()
            charge_id = charge.id

        def evaluate(_):
            with Session(self.engine) as db:
                production = release.avaliar_liberacao_producao(db, charge_id)
                db.commit()
                return production.id

        with ThreadPoolExecutor(max_workers=2) as executor:
            production_ids = list(executor.map(evaluate, range(2)))
        self.assertEqual(len(set(production_ids)), 1)
        with self.engine.connect() as connection:
            self.assertEqual(
                connection.execute(
                    text("SELECT count(*) FROM producoes WHERE orcamento_id=935001")
                ).scalar_one(),
                1,
            )

    def test_concurrent_acceptance_creates_one_charge_without_production(self):
        from models import CobrancaModel, OrcamentoModel, ProducaoModel, PropostaModel
        from services import proposta_comercial_service as commercial

        with Session(self.engine) as db:
            budget = OrcamentoModel(
                id=935001,
                nome_cliente="Synthetic",
                email="synthetic@example.invalid",
                servico="Mix",
                valor_total=Decimal("199.99"),
                status="proposta_enviada",
                observacoes="",
            )
            db.add(budget)
            db.add(self._proposal_model(PropostaModel, budget, status="enviada"))
            db.commit()

        def accept(_):
            with Session(self.engine) as db:
                return commercial.aprovar(db, 935001).status.value

        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertEqual(list(executor.map(accept, range(2))), ["aceita", "aceita"])
        with Session(self.engine) as db:
            self.assertEqual(
                db.query(CobrancaModel)
                .filter(CobrancaModel.proposta_id == 935001)
                .count(),
                1,
            )
            self.assertEqual(
                db.query(ProducaoModel)
                .filter(ProducaoModel.orcamento_id == 935001)
                .count(),
                0,
            )

    def test_concurrent_reconciliation_creates_one_production(self):
        from integrations.mercado_pago import ProviderPaymentResult
        from models import (
            CobrancaModel,
            OrcamentoModel,
            PagamentoModel,
            ProducaoModel,
            PropostaModel,
        )
        from models.enums.financeiro import PagamentoStatus
        from services import mercado_pago_service as mp_service

        with Session(self.engine) as db:
            budget = OrcamentoModel(
                id=935001,
                nome_cliente="Synthetic",
                email="synthetic@example.invalid",
                servico="Mix",
                valor_total=Decimal("199.99"),
                status="aprovado",
                observacoes="",
            )
            proposal = self._proposal_model(PropostaModel, budget, status="aceita")
            charge = CobrancaModel(
                proposta=proposal,
                valor_total=Decimal("199.99"),
                moeda="BRL",
                status="pendente",
            )
            payment = PagamentoModel(
                cobranca=charge,
                tipo="entrada",
                valor=Decimal("99.99"),
                status="pendente",
                provider="mercado_pago",
                provider_order_id="PG-ORDER-935001",
                provider_reference="PG-REFERENCE-935001",
            )
            db.add_all([budget, proposal, charge, payment])
            db.commit()
            payment_id = payment.id

        result = ProviderPaymentResult(
            provider_id="PG-ORDER-935001",
            external_reference="PG-REFERENCE-935001",
            currency="BRL",
            status=PagamentoStatus.APROVADO,
            provider_status="processed",
            status_detail="accredited",
            method="pix",
            amount=Decimal("99.99"),
            approved_at=datetime.now(timezone.utc),
        )

        def reconcile(_):
            with Session(self.engine) as db:
                return mp_service._apply_reconciliation(
                    db,
                    payment_id,
                    result,
                    expected_order_id="PG-ORDER-935001",
                ).current_status

        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(executor.map(reconcile, range(2)))
        self.assertEqual(statuses, ["aprovado", "aprovado"])
        with Session(self.engine) as db:
            self.assertEqual(
                db.query(ProducaoModel)
                .filter(ProducaoModel.orcamento_id == 935001)
                .count(),
                1,
            )
            self.assertEqual(db.get(PagamentoModel, payment_id).status, "aprovado")

    @staticmethod
    def _insert_legacy_fixture(connection, identifier, status):
        connection.execute(
            text(
                """INSERT INTO orcamentos
                   (id, nome_cliente, email, servico, valor_total, status, observacoes)
                   VALUES (:id, 'Synthetic', 'synthetic@example.invalid', 'Mix',
                           199.99, :status, '')"""
            ),
            {"id": identifier, "status": "aprovado" if status == "aceita" else "proposta_enviada"},
        )
        connection.execute(
            text(
                """INSERT INTO propostas
                   (id, orcamento_id, numero, versao, status, cliente_snapshot,
                    objeto, descricao, itens_json, pagamentos_json, condicoes,
                    totais_json)
                   VALUES (:id, :id, :number, 1, :status,
                           CAST(:snapshot AS JSON), 'Mix', 'Synthetic',
                           CAST(:items AS JSON), CAST(:payments AS JSON),
                           'Synthetic', CAST(:totals AS JSON))"""
            ),
            {
                "id": identifier,
                "number": f"PG-{identifier}",
                "status": status,
                "snapshot": (
                    '{"cliente":{"nome":"Synthetic","email":"synthetic@example.invalid"},'
                    f'"orcamento":{{"id":{identifier},"servico":"Mix"}}}}'
                ),
                "items": '[{"descricao":"Mix","quantidade":"1","valor_unitario":"199.99","desconto":"0"}]',
                "payments": '[{"tipo":"integral","titulo":"Legacy","url":"https://example.invalid/legacy","habilitado":true}]',
                "totals": '{"subtotal":"199.99","desconto":"0.00","total":"199.99"}',
            },
        )

    @staticmethod
    def _proposal_model(model, budget, *, status):
        return model(
            id=budget.id,
            orcamento_id=budget.id,
            numero=f"PG-{budget.id}",
            status=status,
            enviada_em=datetime.now(timezone.utc),
            aprovada_em=datetime.now(timezone.utc) if status == "aceita" else None,
            politica_pagamento="entrada_50_50",
            cliente_snapshot={
                "cliente": {
                    "nome": "Synthetic",
                    "email": "synthetic@example.invalid",
                },
                "orcamento": {"id": budget.id, "servico": "Mix"},
            },
            objeto="Mix",
            descricao="Synthetic",
            itens_json=[
                {
                    "descricao": "Mix",
                    "quantidade": "1",
                    "valor_unitario": "199.99",
                    "desconto": "0",
                }
            ],
            pagamentos_json=[],
            condicoes="Synthetic",
            totais_json={
                "subtotal": "199.99",
                "desconto": "0.00",
                "total": "199.99",
            },
        )


if __name__ == "__main__":
    unittest.main()
