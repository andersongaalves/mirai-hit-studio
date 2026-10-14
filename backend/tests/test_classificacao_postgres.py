"""Classification/Order serialization on explicitly disposable PostgreSQL 17."""

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Event

from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

URL = os.getenv("MIRAI_PORTALS_E2E_DATABASE_URL", "")
ACK = os.getenv("MIRAI_PORTALS_E2E_ALLOW", "")
ID = 936001


@unittest.skipUnless(
    URL and ACK == "POSTGRES_17_DISPOSABLE_ONLY", "requires disposable PostgreSQL 17"
)
class ClassificationPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        url = make_url(URL)
        if url.host not in {"localhost", "127.0.0.1"} or "portals_e2e" not in (
            url.database or ""
        ):
            raise RuntimeError("disposable loopback database required")
        cls.engine = create_engine(
            URL, connect_args={"options": "-c lock_timeout=5s -c statement_timeout=15s"}
        )
        with cls.engine.connect() as conn:
            assert (
                int(conn.execute(text("SHOW server_version_num")).scalar_one()) // 10000
                == 17
            )

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        from models import CobrancaModel, OrcamentoModel, PagamentoModel, PropostaModel

        with Session(self.engine) as db:
            budget = OrcamentoModel(
                id=ID,
                nome_cliente="Synthetic",
                email="synthetic@example.com",
                servico="Mix",
                status="aprovado",
            )
            proposal = PropostaModel(
                id=ID,
                orcamento=budget,
                numero="CLASS-SYN",
                status="aceita",
                cliente_snapshot={},
            )
            charge = CobrancaModel(
                id=ID, proposta=proposal, valor_total=Decimal("10"), status="pendente"
            )
            payment = PagamentoModel(
                id=ID,
                cobranca=charge,
                tipo="entrada",
                valor=Decimal("5"),
                status="pendente",
                metodo="pix",
                provider="mercado_pago",
                provider_reference="CLASS-KEY",
                provider_idempotency_key="CLASS-KEY",
            )
            db.add(payment)
            db.commit()

    def tearDown(self):
        from models import (
            CobrancaModel,
            OrcamentoModel,
            PagamentoModel,
            ProducaoModel,
            PropostaModel,
        )
        from models.audit_log import AuditLogModel

        with Session(self.engine) as db:
            db.execute(
                delete(AuditLogModel).where(
                    AuditLogModel.entity_type == "proposal",
                    AuditLogModel.entity_id == str(ID),
                )
            )
            db.execute(delete(ProducaoModel).where(ProducaoModel.orcamento_id == ID))
            db.execute(delete(PagamentoModel).where(PagamentoModel.cobranca_id == ID))
            db.execute(delete(CobrancaModel).where(CobrancaModel.id == ID))
            db.execute(delete(PropostaModel).where(PropostaModel.id == ID))
            db.execute(delete(OrcamentoModel).where(OrcamentoModel.id == ID))
            db.commit()

    @staticmethod
    def classify(engine):
        from schemas.proposta import PropostaClassificacaoUpdate
        from services.classificacao_service import alterar

        with Session(engine) as db:
            return alterar(
                db,
                ID,
                PropostaClassificacaoUpdate(
                    is_test=True, confirmar_historico_financeiro=True
                ),
                None,
            )

    def test_concurrent_classification_is_idempotent(self):
        from models.audit_log import AuditLogModel

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.classify, self.engine) for _ in range(2)]
            assert all(f.result(timeout=20)["is_test"] for f in futures)
        with Session(self.engine) as db:
            assert (
                len(
                    db.scalars(
                        select(AuditLogModel).where(
                            AuditLogModel.action == "proposal.classification_changed",
                            AuditLogModel.entity_id == str(ID),
                        )
                    ).all()
                )
                == 1
            )

    def test_inflight_order_is_preserved_and_later_test_orders_are_blocked(self):
        from integrations.mercado_pago import ProviderPaymentResult
        from models import PagamentoModel
        from models.enums.financeiro import PagamentoStatus
        from services import financial_service, mercado_pago_service

        sending = Event()
        classifying = Event()

        class Provider:
            calls = 0

            def create_pix(self, **kwargs):
                self.calls += 1
                sending.set()
                assert classifying.wait(5)
                return ProviderPaymentResult(
                    provider_id="CLASS-ORDER",
                    external_reference="CLASS-KEY",
                    currency="BRL",
                    amount=Decimal("5"),
                    status=PagamentoStatus.PENDENTE,
                    provider_status="created",
                    status_detail=None,
                    method="pix",
                    approved_at=None,
                )

        provider = Provider()

        def send():
            with Session(self.engine) as db:
                return mercado_pago_service.enviar_pix(
                    db, ID, payer=None, client=provider
                )

        def mark():
            assert sending.wait(5)
            classifying.set()
            return self.classify(self.engine)

        with ThreadPoolExecutor(max_workers=2) as pool:
            send_future = pool.submit(send)
            mark_future = pool.submit(mark)
            assert send_future.result(timeout=20).payment_id == ID
            assert mark_future.result(timeout=20)["is_test"]
        with Session(self.engine) as db:
            assert db.get(PagamentoModel, ID).provider_order_id == "CLASS-ORDER"
            assert db.query(PagamentoModel).filter_by(cobranca_id=ID).count() == 1
            db.add(
                PagamentoModel(
                    id=ID + 1,
                    cobranca_id=ID,
                    tipo="entrada",
                    valor=Decimal("5"),
                    status="pendente",
                    metodo="pix",
                    provider="mercado_pago",
                    provider_reference="CLASS-KEY-BLOCKED",
                    provider_idempotency_key="CLASS-KEY-BLOCKED",
                )
            )
            db.commit()
            with self.assertRaises(financial_service.FinanceiroConflito):
                mercado_pago_service.enviar_pix(db, ID + 1, payer=None, client=provider)
            db.rollback()
        assert provider.calls == 1
