"""Opt-in, non-destructive PostgreSQL validation for phase I.1.

This suite may run against an existing database only with explicit acknowledgement.
It creates synthetic ``i1_test_*`` rows and removes only those rows afterwards.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import os
from threading import Barrier, Lock
import unittest
from uuid import UUID, uuid4

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, delete, func, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import sessionmaker


POSTGRES_URL = os.getenv("MIRAI_I1_DATABASE_URL", "")
EXISTING_DATABASE_ACK = os.getenv("MIRAI_I1_ALLOW_EXISTING_DATABASE", "")
REQUIRED_ACK = "I1_NON_DESTRUCTIVE_ONLY"


def _enabled() -> bool:
    return bool(POSTGRES_URL) and EXISTING_DATABASE_ACK == REQUIRED_ACK


@unittest.skipUnless(
    _enabled(),
    "set MIRAI_I1_DATABASE_URL and acknowledge I1_NON_DESTRUCTIVE_ONLY",
)
class PostgreSQLI1Tests(unittest.TestCase):
    @staticmethod
    def _users_digest(connection) -> str:
        rows = connection.execute(
            text(
                """
                SELECT id, username, password_hash, is_admin, ativo, role,
                       created_at, updated_at
                FROM usuarios ORDER BY id
                """
            )
        ).all()
        digest = hashlib.sha256()
        for row in rows:
            digest.update(repr(tuple(row)).encode("utf-8"))
        return f"{len(rows)}:{digest.hexdigest()}"

    @classmethod
    def setUpClass(cls):
        url = make_url(POSTGRES_URL)
        if not url.drivername.startswith("postgresql"):
            raise RuntimeError("I.1 requires PostgreSQL")
        cls.engine = create_engine(
            POSTGRES_URL,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 10},
        )
        cls.sessions = sessionmaker(bind=cls.engine, expire_on_commit=False)
        with cls.engine.connect() as connection:
            tables = set(inspect(connection).get_table_names())
            required = {
                "alembic_version",
                "cobrancas",
                "pagamentos",
                "provider_webhook_events",
                "ai_conversations",
                "ai_messages",
                "ai_email_threads",
                "ai_briefings",
                "usuarios",
            }
            if not required <= tables:
                raise RuntimeError("I.1 existing database schema is incomplete")
            cls.database_name = connection.execute(
                text("SELECT current_database()")
            ).scalar_one()
            cls.users_before = cls._users_digest(connection)

    @classmethod
    def tearDownClass(cls):
        try:
            with cls.engine.connect() as connection:
                if cls._users_digest(connection) != cls.users_before:
                    raise AssertionError("I.1 changed protected user data")
        finally:
            cls.engine.dispose()

    def setUp(self):
        self.token = uuid4().hex
        self.prefix = f"i1_test_{self.token}"

    def tearDown(self):
        self._cleanup()

    def _cleanup(self):
        """Delete only rows identifiable as fixtures from this test."""
        from models import (
            AIBriefingModel,
            AIConversationModel,
            AIEmailThreadModel,
            AIMessageModel,
            AIUsageEventModel,
            ClienteModel,
            CobrancaModel,
            OrcamentoModel,
            PagamentoModel,
            PropostaModel,
            ProviderWebhookEventModel,
        )

        with self.sessions.begin() as db:
            conversation_ids = list(
                db.scalars(
                    select(AIConversationModel.id).where(
                        (AIConversationModel.external_thread_id.like(f"{self.prefix}%"))
                        | (AIConversationModel.sender_reference.like(f"{self.prefix}%"))
                    )
                )
            )
            if conversation_ids:
                db.execute(
                    delete(AIUsageEventModel).where(
                        AIUsageEventModel.conversation_id.in_(conversation_ids)
                    )
                )
                db.execute(
                    delete(AIBriefingModel).where(
                        AIBriefingModel.conversation_id.in_(conversation_ids)
                    )
                )
                db.execute(
                    delete(AIEmailThreadModel).where(
                        AIEmailThreadModel.conversation_id.in_(conversation_ids)
                    )
                )
                db.execute(
                    delete(AIMessageModel).where(
                        AIMessageModel.conversation_id.in_(conversation_ids)
                    )
                )
                db.execute(
                    delete(AIConversationModel).where(
                        AIConversationModel.id.in_(conversation_ids)
                    )
                )

            proposal_ids = list(
                db.scalars(
                    select(PropostaModel.id).where(
                        PropostaModel.numero.like(f"I1-{self.token[:12]}%")
                    )
                )
            )
            charge_ids = (
                list(
                    db.scalars(
                        select(CobrancaModel.id).where(
                            CobrancaModel.proposta_id.in_(proposal_ids)
                        )
                    )
                )
                if proposal_ids
                else []
            )
            db.execute(
                delete(ProviderWebhookEventModel).where(
                    (ProviderWebhookEventModel.provider_request_id.like(f"{self.prefix}%"))
                    | (ProviderWebhookEventModel.resource_id.like(f"{self.prefix}%"))
                )
            )
            if charge_ids:
                db.execute(
                    delete(PagamentoModel).where(
                        PagamentoModel.cobranca_id.in_(charge_ids)
                    )
                )
                db.execute(
                    delete(CobrancaModel).where(CobrancaModel.id.in_(charge_ids))
                )
            if proposal_ids:
                db.execute(delete(PropostaModel).where(PropostaModel.id.in_(proposal_ids)))
            db.execute(
                delete(OrcamentoModel).where(
                    OrcamentoModel.email == f"{self.prefix}@example.com"
                )
            )
            db.execute(
                delete(ClienteModel).where(
                    ClienteModel.email == f"{self.prefix}@example.com"
                )
            )

    def _financial_graph(self, total: Decimal = Decimal("199.99")):
        from models import ClienteModel, CobrancaModel, OrcamentoModel, PropostaModel

        with self.sessions.begin() as db:
            client = ClienteModel(
                nome="I1_TEST Cliente",
                email=f"{self.prefix}@example.com",
                telefone=None,
            )
            db.add(client)
            db.flush()
            budget = OrcamentoModel(
                nome_cliente="I1_TEST Cliente",
                email=client.email,
                servico="I1_TEST",
                valor_total=float(total),
                detalhes="I1_TEST fixture PostgreSQL",
                status="aprovado",
                cliente_id=client.id,
            )
            db.add(budget)
            db.flush()
            proposal = PropostaModel(
                orcamento_id=budget.id,
                numero=f"I1-{self.token[:12]}",
                versao=1,
                status="aceita",
                cliente_snapshot={"nome": "I1_TEST Cliente", "email": client.email},
                objeto="I1_TEST",
                descricao="I1_TEST fixture PostgreSQL",
                itens_json=[
                    {
                        "descricao": "I1_TEST",
                        "quantidade": 1,
                        "valor_unitario": f"{total:.2f}",
                        "desconto": "0.00",
                        "subtotal": f"{total:.2f}",
                    }
                ],
                pagamentos_json=[],
                condicoes="I1_TEST",
                totais_json={"total": f"{total:.2f}"},
            )
            db.add(proposal)
            db.flush()
            charge = CobrancaModel(
                proposta_id=proposal.id,
                cliente_id=client.id,
                valor_total=total,
                moeda="BRL",
                status="pendente",
            )
            db.add(charge)
            db.flush()
            return client.id, budget.id, proposal.id, charge.id

    def _site_conversation(self, suffix: str, *, clock=None):
        from schemas.ai import ConversationCreate, ConversationMode
        from services.ai_conversation_service import ConversationService

        kwargs = {"clock": clock, "lease_seconds": 10} if clock else {}
        service = ConversationService(self.sessions, **kwargs)
        thread = f"{self.prefix}_{suffix}"
        conversation_id = service.create(
            ConversationCreate(
                channel="site",
                mode=ConversationMode.AUTONOMOUS,
                external_thread_id=thread,
                sender_reference=f"{self.prefix}_sender",
            )
        )
        return service, conversation_id, thread

    def test_schema_metadata_constraints_indexes_types_and_revision(self):
        import models  # noqa: F401
        from database import Base
        from scripts.bootstrap_database import migration_config

        with self.engine.connect() as connection:
            context = MigrationContext.configure(
                connection, opts={"compare_type": True}
            )
            self.assertEqual(compare_metadata(context, Base.metadata), [])
            head = ScriptDirectory.from_config(migration_config()).get_current_head()
            self.assertEqual(context.get_current_revision(), head)
            isolation = connection.execute(
                text("SHOW transaction_isolation")
            ).scalar_one()
            self.assertEqual(isolation, "read committed")

            numeric = connection.execute(
                text(
                    """
                    SELECT table_name, column_name, numeric_precision, numeric_scale
                    FROM information_schema.columns
                    WHERE table_schema='public'
                      AND (table_name, column_name) IN (
                        ('cobrancas','valor_total'), ('pagamentos','valor')
                      )
                    ORDER BY table_name, column_name
                    """
                )
            ).all()
            self.assertEqual(
                numeric,
                [
                    ("cobrancas", "valor_total", 12, 2),
                    ("pagamentos", "valor", 12, 2),
                ],
            )
            constraints = set(
                connection.execute(
                    text(
                        """
                        SELECT conname FROM pg_constraint
                        WHERE conname = ANY(:names)
                        """
                    ),
                    {
                        "names": [
                            "uq_cobrancas_proposta_id",
                            "uq_pagamentos_provider_payment_id",
                            "uq_pagamentos_provider_idempotency_key",
                            "uq_provider_webhook_events_deduplication_key",
                            "uq_ai_message_inbound",
                            "uq_ai_message_reply",
                            "uq_ai_email_thread_root_message",
                        ]
                    },
                ).scalars()
            )
            self.assertEqual(len(constraints), 7)
            indexes = set(
                connection.execute(
                    text(
                        """
                        SELECT indexname FROM pg_indexes
                        WHERE schemaname='public' AND indexname = ANY(:names)
                        """
                    ),
                    {
                        "names": [
                            "ix_cobrancas_status",
                            "ix_pagamentos_status",
                            "ix_pagamentos_reconciliation_status",
                            "ix_provider_webhook_events_resource_id",
                            "ix_ai_conversation_status",
                            "ix_ai_message_history",
                            "ix_ai_message_pending",
                        ]
                    },
                ).scalars()
            )
            self.assertEqual(len(indexes), 7)

    def test_decimal_unique_charge_and_transaction_rollback(self):
        from models import CobrancaModel, PagamentoModel
        from services import financial_service

        _, _, proposal_id, charge_id = self._financial_graph()
        with self.sessions() as db:
            stored = db.get(CobrancaModel, charge_id)
            self.assertIsInstance(stored.valor_total, Decimal)
            self.assertEqual(stored.valor_total, Decimal("199.99"))
        self.assertEqual(
            financial_service.dividir_50_50(Decimal("199.99")),
            (Decimal("99.99"), Decimal("100.00")),
        )

        with self.assertRaises(IntegrityError):
            with self.sessions.begin() as db:
                db.add(
                    CobrancaModel(
                        proposta_id=proposal_id,
                        valor_total=Decimal("199.99"),
                        moeda="BRL",
                        status="pendente",
                    )
                )
                db.flush()

        with self.sessions.begin() as db:
            db.add(
                PagamentoModel(
                    cobranca_id=charge_id,
                    tipo="integral",
                    valor=Decimal("199.99"),
                    status="pendente",
                    provider="i1_fake",
                    provider_reference=f"{self.prefix}_unique_a",
                    provider_idempotency_key=f"{self.prefix}_idempotency",
                )
            )
        with self.assertRaises(IntegrityError):
            with self.sessions.begin() as db:
                db.add(
                    PagamentoModel(
                        cobranca_id=charge_id,
                        tipo="integral",
                        valor=Decimal("199.99"),
                        status="pendente",
                        provider="i1_fake",
                        provider_reference=f"{self.prefix}_unique_b",
                        provider_idempotency_key=f"{self.prefix}_idempotency",
                    )
                )
                db.flush()

        try:
            with self.sessions.begin() as db:
                db.add(
                    PagamentoModel(
                        cobranca_id=charge_id,
                        tipo="integral",
                        valor=Decimal("199.99"),
                        status="pendente",
                        provider_reference=f"{self.prefix}_rollback",
                    )
                )
                db.flush()
                raise RuntimeError("i1_test_forced_rollback")
        except RuntimeError:
            pass
        with self.sessions() as db:
            count = db.scalar(
                select(func.count())
                .select_from(PagamentoModel)
                .where(PagamentoModel.provider_reference == f"{self.prefix}_rollback")
            )
            self.assertEqual(count, 0)

    def test_real_row_lock_and_financial_overpayment_serialization(self):
        from models import CobrancaModel, PagamentoModel
        from services import financial_service

        _, _, _, charge_id = self._financial_graph(Decimal("100.00"))
        locked = Barrier(2)
        released = Barrier(2)
        outcome = []

        def blocked_reader():
            with self.sessions() as db:
                try:
                    with db.begin():
                        db.execute(text("SET LOCAL lock_timeout = '750ms'"))
                        locked.wait(timeout=5)
                        db.scalar(
                            select(CobrancaModel)
                            .where(CobrancaModel.id == charge_id)
                            .with_for_update()
                        )
                except DBAPIError as error:
                    outcome.append(
                        getattr(error.orig, "sqlstate", None)
                        or getattr(error.orig, "pgcode", None)
                    )
                finally:
                    released.wait(timeout=5)

        with self.sessions() as first:
            with first.begin():
                first.scalar(
                    select(CobrancaModel)
                    .where(CobrancaModel.id == charge_id)
                    .with_for_update()
                )
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(blocked_reader)
                    locked.wait(timeout=5)
                    released.wait(timeout=5)
                    future.result(timeout=5)
        self.assertEqual(outcome, ["55P03"])

        barrier = Barrier(2)

        def approve(reference):
            try:
                with self.sessions.begin() as db:
                    db.execute(text("SET LOCAL lock_timeout = '2s'"))
                    barrier.wait(timeout=5)
                    financial_service.registrar_pagamento(
                        db,
                        charge_id,
                        tipo="entrada",
                        valor=Decimal("60.00"),
                        status="aprovado",
                        provider="i1_fake",
                        provider_reference=reference,
                    )
                return "approved"
            except financial_service.FinanceiroConflito:
                return "conflict"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    approve,
                    [f"{self.prefix}_pay_a", f"{self.prefix}_pay_b"],
                )
            )
        self.assertCountEqual(results, ["approved", "conflict"])
        with self.sessions() as db:
            approved = db.scalars(
                select(PagamentoModel).where(
                    PagamentoModel.cobranca_id == charge_id,
                    PagamentoModel.status == "aprovado",
                )
            ).all()
            self.assertEqual(len(approved), 1)
            self.assertEqual(approved[0].valor, Decimal("60.00"))
            self.assertEqual(db.get(CobrancaModel, charge_id).status, "parcialmente_paga")

    def test_webhook_concurrency_is_state_idempotent_with_fake_provider(self):
        from integrations.mercado_pago import ProviderPaymentResult
        from models import CobrancaModel, PagamentoModel, ProviderWebhookEventModel
        from models.enums.financeiro import PagamentoStatus
        from services.mercado_pago_webhook_service import process_webhook

        _, _, _, charge_id = self._financial_graph(Decimal("100.00"))
        provider_order_id = f"{self.prefix}_order"
        provider_reference = f"{self.prefix}_reference"
        with self.sessions.begin() as db:
            payment = PagamentoModel(
                cobranca_id=charge_id,
                tipo="integral",
                valor=Decimal("100.00"),
                status="pendente",
                metodo="pix",
                provider="mercado_pago",
                provider_order_id=provider_order_id,
                provider_reference=provider_reference,
                provider_idempotency_key=f"{self.prefix}_key",
            )
            db.add(payment)

        result = ProviderPaymentResult(
            provider_id=provider_order_id,
            external_reference=provider_reference,
            currency="BRL",
            status=PagamentoStatus.APROVADO,
            provider_status="approved",
            status_detail="accredited",
            method="pix",
            amount=Decimal("100.00"),
            approved_at=datetime.now(timezone.utc),
        )

        class FakeProvider:
            def __init__(self):
                self.calls = 0
                self.lock = Lock()

            def get_order(self, provider_id):
                self.assert_id(provider_id)
                with self.lock:
                    self.calls += 1
                return result

            @staticmethod
            def assert_id(provider_id):
                if provider_id != provider_order_id:
                    raise AssertionError("unexpected provider id")

        provider = FakeProvider()
        barrier = Barrier(2)

        def deliver():
            with self.sessions() as db:
                barrier.wait(timeout=5)
                return process_webhook(
                    db,
                    resource_id=provider_order_id,
                    event_type="order",
                    action="payment.updated",
                    provider_event_id=f"{self.prefix}_event",
                    provider_request_id=f"{self.prefix}_request",
                    signature_timestamp="1700000000",
                    client=provider,
                )

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = [future.result(timeout=10) for future in [
                executor.submit(deliver), executor.submit(deliver)
            ]]
        self.assertTrue(all(item.status == "processed" for item in outcomes))
        self.assertEqual(sum(item.duplicate for item in outcomes), 1)
        with self.sessions() as db:
            self.assertEqual(
                db.scalar(
                    select(func.count())
                    .select_from(ProviderWebhookEventModel)
                    .where(
                        ProviderWebhookEventModel.provider_request_id
                        == f"{self.prefix}_request"
                    )
                ),
                1,
            )
            payment = db.scalar(
                select(PagamentoModel).where(
                    PagamentoModel.provider_order_id == provider_order_id
                )
            )
            self.assertEqual(payment.status, "aprovado")
            self.assertEqual(db.get(CobrancaModel, charge_id).status, "paga")

    def test_ai_inbound_lease_recovery_completion_and_late_response(self):
        from models.ai import AIMessageModel
        from schemas.ai import DecisionAction, HandoffReason, InboundMessage
        from services.ai_conversation_service import (
            Claim,
            ConversationError,
            ProcessingResult,
        )
        from services.ai_orchestrator import Decision

        now = [datetime.now(timezone.utc)]
        service, conversation_id, thread = self._site_conversation(
            "lease", clock=lambda: now[0]
        )
        inbound = InboundMessage(
            channel="site",
            external_message_id=f"{self.prefix}_inbound",
            external_thread_id=thread,
            sender_reference=f"{self.prefix}_sender",
            text="I1_TEST mensagem sintetica",
            received_at=now[0],
        )
        barrier = Barrier(2)

        def receive_once():
            barrier.wait(timeout=5)
            return service.receive(conversation_id, inbound)

        with ThreadPoolExecutor(max_workers=2) as executor:
            message_ids = list(executor.map(lambda _: receive_once(), range(2)))
        self.assertEqual(len(set(message_ids)), 1)
        message_id = message_ids[0]

        barrier = Barrier(2)

        def claim_once():
            barrier.wait(timeout=5)
            try:
                return service.claim(conversation_id, message_id)
            except ConversationError as error:
                return str(error)

        with ThreadPoolExecutor(max_workers=2) as executor:
            claims = list(executor.map(lambda _: claim_once(), range(2)))
        active_claim = next(item for item in claims if isinstance(item, Claim))
        self.assertIn("processing_conflict", claims)

        now[0] += timedelta(seconds=11)
        recovered = service.claim(conversation_id, message_id)
        self.assertIsInstance(recovered, Claim)
        with self.assertRaisesRegex(ConversationError, "processing_conflict"):
            service.complete(
                active_claim,
                Decision(DecisionAction.REPLY, text="I1_TEST stale"),
            )
        completed = service.complete(
            recovered,
            Decision(DecisionAction.REPLY, text="I1_TEST resposta valida"),
        )
        self.assertEqual(completed.action, DecisionAction.REPLY)
        self.assertIsInstance(
            service.claim(conversation_id, message_id), ProcessingResult
        )

        second = service.receive(
            conversation_id,
            inbound.model_copy(
                update={"external_message_id": f"{self.prefix}_late"}
            ),
        )
        late_claim = service.claim(conversation_id, second)
        service.handoff(conversation_id, HandoffReason.MANUAL_REQUEST)
        with self.assertRaisesRegex(ConversationError, "processing_conflict"):
            service.complete(
                late_claim,
                Decision(DecisionAction.REPLY, text="I1_TEST resposta tardia"),
            )
        with self.sessions() as db:
            self.assertEqual(
                db.scalar(
                    select(func.count())
                    .select_from(AIMessageModel)
                    .where(
                        AIMessageModel.conversation_id == conversation_id,
                        AIMessageModel.reply_to_id == second,
                    )
                ),
                0,
            )

    def test_email_and_briefing_idempotency(self):
        from models import (
            AIBriefingModel,
            AIConversationModel,
            AIMessageModel,
            ClienteModel,
            OrcamentoModel,
        )
        from schemas.ai import ConversationMode, ProviderResponse
        from services.ai_briefing_service import AIBriefingService
        from services.ai_conversation_service import ConversationService
        from services.ai_email_service import AIEmailError, AIEmailService
        from services.ai_tools import ToolExecutionContext

        class FakeAI:
            def __init__(self):
                self.calls = 0
                self.lock = Lock()

            def generate(self, _incoming):
                with self.lock:
                    self.calls += 1
                return ProviderResponse(text="I1_TEST resposta")

        fixture_prefix = self.prefix

        class FakeEmail:
            def __init__(self):
                self.sent = []
                self.lock = Lock()

            def retrieve_received(self, _email_id):
                raise AssertionError("unexpected retrieval")

            def send_reply(self, **payload):
                with self.lock:
                    self.sent.append(payload["idempotency_key"])
                    return f"{fixture_prefix}_sent_{len(self.sent)}"

        ai = FakeAI()
        email = FakeEmail()
        core = ConversationService(self.sessions, ai)
        email_service = AIEmailService(
            core,
            email,
            sender_address="mirai-i1@example.com",
            limiter=lambda _identity, _limit, _window: (True, 0),
        )
        payload = {
            "type": "email.received",
            "data": {
                "email_id": f"{self.prefix}_email",
                "from": f"{self.prefix}@example.com",
                "to": ["mirai-i1@example.com"],
                "subject": "I1_TEST",
                "message_id": f"<{self.prefix}@example.com>",
                "text": "I1_TEST mensagem",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        barrier = Barrier(2)

        def handle_email():
            barrier.wait(timeout=5)
            try:
                return email_service.handle(
                    payload, request_id=f"{self.prefix}_req"
                )
            except Exception as error:
                return error

        with ThreadPoolExecutor(max_workers=2) as executor:
            concurrent = list(executor.map(lambda _: handle_email(), range(2)))
        accepted = [item for item in concurrent if not isinstance(item, Exception)]
        errors = [item for item in concurrent if isinstance(item, Exception)]
        self.assertTrue(accepted)
        self.assertTrue(all(isinstance(item, AIEmailError) for item in errors))
        self.assertTrue(
            all(str(item) in {"processing_conflict", "storage_unavailable"} for item in errors)
        )
        first = accepted[0]
        second = email_service.handle(payload, request_id=f"{self.prefix}_req")
        self.assertEqual(first.conversation_id, second.conversation_id)
        self.assertTrue(second.duplicate)
        self.assertEqual(ai.calls, 1)
        self.assertEqual(len(email.sent), 1)

        service, conversation_id, thread = self._site_conversation("briefing")
        now = datetime.now(timezone.utc)
        with self.sessions.begin() as db:
            message = AIMessageModel(
                id=str(uuid4()),
                conversation_id=conversation_id,
                direction="inbound",
                role="user",
                channel="site",
                external_message_id=f"{self.prefix}_briefing_message",
                content="Confirmo o envio do orcamento",
                received_at=now,
                created_at=now,
                processing_status="pending",
            )
            db.add(message)
            db.add(
                AIBriefingModel(
                    conversation_id=conversation_id,
                    interest="I1_TEST",
                    contact_name="I1_TEST Cliente",
                    contact_email=f"{self.prefix}@example.com",
                    data_json={},
                    status="draft",
                    created_at=now,
                    updated_at=now,
                )
            )
        context = ToolExecutionContext(
            conversation_id=UUID(conversation_id),
            message_id=UUID(message.id),
            mode=ConversationMode.AUTONOMOUS,
            source="site",
        )
        briefing = AIBriefingService(self.sessions)
        barrier = Barrier(2)

        def submit_once():
            barrier.wait(timeout=5)
            return briefing.submit(context, {})

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: submit_once(), range(2)))
        self.assertTrue(all(item.submitted for item in results))
        with self.sessions() as db:
            row = db.get(AIBriefingModel, conversation_id)
            self.assertIsNotNone(row.orcamento_id)
            self.assertEqual(
                db.scalar(
                    select(func.count())
                    .select_from(OrcamentoModel)
                    .where(
                        OrcamentoModel.email
                        == f"{self.prefix}@example.com"
                    )
                ),
                1,
            )
            self.assertEqual(
                db.scalar(
                    select(func.count())
                    .select_from(ClienteModel)
                    .where(ClienteModel.email == f"{self.prefix}@example.com")
                ),
                1,
            )
            self.assertIsNotNone(db.get(AIConversationModel, conversation_id).cliente_id)

    def test_rls_inventory_non_owner_denial_and_application_role(self):
        from schemas.ai import ConversationCreate, ConversationMode
        from services.ai_conversation_service import ConversationService

        service = ConversationService(self.sessions)
        conversation_id = service.create(
            ConversationCreate(
                channel="site",
                mode=ConversationMode.HUMAN,
                external_thread_id=f"{self.prefix}_rls",
                sender_reference=f"{self.prefix}_sender",
            )
        )
        role = f"i1_test_rls_{self.token[:16]}"
        created = False
        try:
            with self.engine.begin() as connection:
                attrs = connection.execute(
                    text(
                        """
                        SELECT rolsuper, rolcreaterole, rolbypassrls,
                               EXISTS (
                                 SELECT 1 FROM pg_class
                                 WHERE relkind='r' AND relowner=(
                                   SELECT oid FROM pg_roles WHERE rolname=current_user
                                 )
                               )
                        FROM pg_roles WHERE rolname=current_user
                        """
                    )
                ).one()
                self.assertFalse(attrs[0])
                self.assertTrue(attrs[2])
                self.assertTrue(attrs[3])
                inventory = connection.execute(
                    text(
                        """
                        SELECT relname, relrowsecurity, relforcerowsecurity
                        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                        WHERE n.nspname='public' AND relkind='r' AND relname = ANY(:tables)
                        ORDER BY relname
                        """
                    ),
                    {
                        "tables": [
                            "ai_conversations",
                            "ai_messages",
                            "ai_email_threads",
                            "ai_briefings",
                            "ai_usage_events",
                        ]
                    },
                ).all()
                self.assertEqual(len(inventory), 5)
                self.assertTrue(all(enabled and not forced for _, enabled, forced in inventory))
                policies = connection.execute(
                    text(
                        """
                        SELECT tablename, policyname, cmd, roles, qual, with_check
                        FROM pg_policies
                        WHERE schemaname='public' AND tablename = ANY(:tables)
                        """
                    ),
                    {"tables": [row[0] for row in inventory]},
                ).all()
                self.assertEqual(policies, [])
                if not attrs[1]:
                    self.skipTest("application role cannot create temporary RLS role")
                connection.exec_driver_sql(f'CREATE ROLE "{role}" NOLOGIN NOBYPASSRLS')
                created = True
                connection.exec_driver_sql(f'GRANT "{role}" TO CURRENT_USER')
                connection.exec_driver_sql(f'GRANT USAGE ON SCHEMA public TO "{role}"')
                connection.exec_driver_sql(
                    f'GRANT SELECT ON TABLE public.ai_conversations TO "{role}"'
                )
            with self.engine.connect() as restricted:
                with restricted.begin():
                    restricted.exec_driver_sql(f'SET LOCAL ROLE "{role}"')
                    visible = restricted.execute(
                        text(
                            "SELECT count(*) FROM public.ai_conversations WHERE id=:id"
                        ),
                        {"id": conversation_id},
                    ).scalar_one()
                    self.assertEqual(visible, 0)
        finally:
            if created:
                with self.engine.begin() as connection:
                    connection.exec_driver_sql(
                        f'REVOKE ALL ON TABLE public.ai_conversations FROM "{role}"'
                    )
                    connection.exec_driver_sql(
                        f'REVOKE USAGE ON SCHEMA public FROM "{role}"'
                    )
                    connection.exec_driver_sql(f'REVOKE "{role}" FROM CURRENT_USER')
                    connection.exec_driver_sql(f'DROP ROLE IF EXISTS "{role}"')


if __name__ == "__main__":
    unittest.main(verbosity=2)
