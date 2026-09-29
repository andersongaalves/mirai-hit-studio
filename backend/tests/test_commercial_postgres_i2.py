"""Opt-in connected browser/HTTP/PostgreSQL validation for phase I.2."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx
import resend
from sqlalchemy import delete, event, func, inspect, select, text
from sqlalchemy.engine import make_url

from commercial_i2_support import PaymentTransport, local_frontend_server, local_server, signed_webhook


POSTGRES_URL = os.getenv("MIRAI_I2_DATABASE_URL", "")
ACK = os.getenv("MIRAI_I2_ALLOW_ACTIVE_DATABASE", "")


@unittest.skipUnless(bool(POSTGRES_URL) and ACK == "I2_SYNTHETIC_FIXTURES_ONLY", "I.2 PostgreSQL opt-in required")
class CommercialPostgresI2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not make_url(POSTGRES_URL).drivername.startswith("postgresql"):
            raise RuntimeError("I.2 requires PostgreSQL")
        from database import engine, SessionLocal
        from main import app
        from models import UsuarioModel
        from core.config import settings
        from core.security import get_password_hash
        from routers.checkout import get_mercado_pago_client as checkout_provider
        from routers.webhooks import get_mercado_pago_client as webhook_provider
        from services import mercado_pago_service
        configured_url = make_url(POSTGRES_URL)
        engine_url = make_url(str(engine.url))
        configured_target = (configured_url.drivername, configured_url.host,
                             configured_url.port, configured_url.database)
        engine_target = (engine_url.drivername, engine_url.host,
                         engine_url.port, engine_url.database)
        if configured_target != engine_target:
            raise RuntimeError("I.2 app database differs from the authorized target")
        cls.engine, cls.SessionLocal, cls.app = engine, SessionLocal, app
        cls.db_errors = []

        def capture_db_error(context):
            original = context.original_exception
            diagnostic = getattr(original, "diag", None)
            cls.db_errors.append({
                "type": type(original).__name__,
                "sqlstate": getattr(original, "sqlstate", None),
                "constraint": getattr(diagnostic, "constraint_name", None),
                "message": getattr(diagnostic, "message_primary", None),
            })

        cls.capture_db_error = capture_db_error
        event.listen(engine, "handle_error", capture_db_error)
        settings.MERCADO_PAGO_WEBHOOK_SECRET = "i2-synthetic-webhook-secret"
        settings.MERCADO_PAGO_PUBLIC_KEY = "TEST-I2-NOT-REAL"
        settings.PUBLIC_FRONTEND_URL = "http://127.0.0.1:5500"
        with engine.connect() as connection:
            if connection.execute(text("select version_num from alembic_version")).scalar_one() != "b8c41e7d290a":
                raise RuntimeError("I.2 database is not at expected head")
            columns = {item["name"] for item in inspect(connection).get_columns("orcamentos")}
            if not {"idempotency_key", "request_hash"} <= columns:
                raise RuntimeError("I.2 idempotency schema missing")
        cls.token = uuid4().hex
        cls.prefix = f"i2_{cls.token}"
        cls.name = f"I2 Browser {cls.token[:8]}"
        cls.email = f"{cls.prefix}@example.com"
        cls.username = f"i2op{cls.token[:20]}"
        cls.password = "I2-only-password!"
        cls.users_before = cls._users_digest(exclude_username=cls.username)
        with SessionLocal.begin() as db:
            db.add(UsuarioModel(username=cls.username, password_hash=get_password_hash(cls.password),
                                is_admin=True, role="admin", ativo=True))
        cls.temp = tempfile.TemporaryDirectory(prefix="mirai-i2-connected-")
        os.environ["PROPOSTA_PDF_DIR"] = cls.temp.name
        os.environ["RATE_LIMIT_DB"] = str(Path(cls.temp.name) / "rate.sqlite3")
        cls.transport = PaymentTransport()
        from integrations.mercado_pago import MercadoPagoClient
        cls.provider = MercadoPagoClient(access_token="TEST-I2-NOT-REAL", session=cls.transport)
        app.dependency_overrides[checkout_provider] = lambda: cls.provider
        app.dependency_overrides[webhook_provider] = lambda: cls.provider
        cls.stack = ExitStack()
        cls.stack.enter_context(patch.object(resend.Emails, "send", return_value={"id":"i2-fake-email"}))
        cls.stack.enter_context(patch.object(mercado_pago_service, "MercadoPagoClient", return_value=cls.provider))
        cls.stack.enter_context(patch("core.http_security.allow_request", return_value=(True, 0)))
        cls.server = cls.stack.enter_context(local_server(app, port=8000))
        frontend_root = Path(__file__).resolve().parents[2] / "frontend"
        cls.frontend = cls.stack.enter_context(local_frontend_server(frontend_root, port=5500))
        cls.http = cls.stack.enter_context(httpx.Client(base_url=cls.server, timeout=60, trust_env=False))
        services = cls.http.get("/servicos")
        if services.status_code != 200 or not services.json():
            raise RuntimeError("I.2 requires at least one existing catalog service")

    @classmethod
    def _users_digest(cls, exclude_username=None):
        query = "select id, username, password_hash, is_admin, ativo, role, created_at, updated_at from usuarios"
        params = {}
        if exclude_username:
            query += " where username <> :username"
            params["username"] = exclude_username
        query += " order by id"
        with cls.engine.connect() as connection:
            rows = connection.execute(text(query), params).all()
        digest = hashlib.sha256()
        for row in rows:
            digest.update(repr(tuple(row)).encode())
        return f"{len(rows)}:{digest.hexdigest()}"

    @classmethod
    def _browser(cls, mode, **values):
        root = Path(__file__).resolve().parents[2]
        env = {**os.environ, "I2_BROWSER_MODE": mode,
               "NODE_PATH": r"C:\Users\SadBox\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules",
               "I2_NAME": cls.name, "I2_EMAIL": cls.email,
               "I2_USERNAME": cls.username, "I2_PASSWORD": cls.password,
               **{f"I2_{key.upper()}": str(value) for key, value in values.items()}}
        result = subprocess.run([r"D:\node.exe", str(root / "frontend/tests/commercial_postgres_i2.cjs")],
                                cwd=root, env=env, capture_output=True, text=True, timeout=120)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        line = next(line for line in result.stdout.splitlines() if line.startswith("I2_RESULT "))
        return json.loads(line.removeprefix("I2_RESULT "))

    @classmethod
    def tearDownClass(cls):
        try:
            cls._cleanup()
            remaining = cls._fixture_counts()
            if any(remaining.values()):
                raise AssertionError(f"I.2 fixture cleanup incomplete: {remaining}")
            if cls._users_digest() != cls.users_before:
                raise AssertionError("I.2 changed protected users")
        finally:
            cls.stack.close()
            cls.temp.cleanup()
            event.remove(cls.engine, "handle_error", cls.capture_db_error)
            cls.engine.dispose()

    @classmethod
    def _cleanup(cls):
        from models import (AuditLogModel, ClienteModel, CobrancaModel, OrcamentoModel,
                            PagamentoModel, ProducaoModel, PropostaModel, ProviderWebhookEventModel, UsuarioModel)
        with cls.SessionLocal.begin() as db:
            budgets = list(db.scalars(select(OrcamentoModel.id).where(
                OrcamentoModel.email.startswith(cls.prefix, autoescape=True)
            )))
            proposals = list(db.scalars(select(PropostaModel.id).where(PropostaModel.orcamento_id.in_(budgets)))) if budgets else []
            charges = list(db.scalars(select(CobrancaModel.id).where(CobrancaModel.proposta_id.in_(proposals)))) if proposals else []
            payments = list(db.scalars(select(PagamentoModel.id).where(PagamentoModel.cobranca_id.in_(charges)))) if charges else []
            if payments:
                db.execute(delete(ProviderWebhookEventModel).where(ProviderWebhookEventModel.pagamento_id.in_(payments)))
            if charges:
                db.execute(delete(PagamentoModel).where(PagamentoModel.cobranca_id.in_(charges)))
                db.execute(delete(CobrancaModel).where(CobrancaModel.id.in_(charges)))
            if budgets:
                db.execute(delete(ProducaoModel).where(ProducaoModel.orcamento_id.in_(budgets)))
            if proposals:
                db.execute(delete(AuditLogModel).where((AuditLogModel.entity_type == "proposal") & AuditLogModel.entity_id.in_([str(x) for x in proposals])))
                db.execute(delete(PropostaModel).where(PropostaModel.id.in_(proposals)))
            if budgets:
                db.execute(delete(OrcamentoModel).where(OrcamentoModel.id.in_(budgets)))
            db.execute(delete(ClienteModel).where(ClienteModel.email.startswith(cls.prefix, autoescape=True)))
            db.execute(delete(AuditLogModel).where(AuditLogModel.actor_user_id == select(UsuarioModel.id).where(UsuarioModel.username == cls.username).scalar_subquery()))
            db.execute(delete(UsuarioModel).where(UsuarioModel.username == cls.username))

    @classmethod
    def _fixture_counts(cls):
        from models import (ClienteModel, CobrancaModel, OrcamentoModel, PagamentoModel,
                            ProducaoModel, PropostaModel, ProviderWebhookEventModel)
        with cls.SessionLocal() as db:
            budgets = select(OrcamentoModel.id).where(
                OrcamentoModel.email.startswith(cls.prefix, autoescape=True)
            )
            proposals = select(PropostaModel.id).where(PropostaModel.orcamento_id.in_(budgets))
            charges = select(CobrancaModel.id).where(CobrancaModel.proposta_id.in_(proposals))
            payments = select(PagamentoModel.id).where(PagamentoModel.cobranca_id.in_(charges))
            return {
                "clientes": db.scalar(select(func.count()).select_from(ClienteModel).where(
                    ClienteModel.email.startswith(cls.prefix, autoescape=True)
                )),
                "orcamentos": db.scalar(select(func.count()).select_from(OrcamentoModel).where(
                    OrcamentoModel.id.in_(budgets)
                )),
                "propostas": db.scalar(select(func.count()).select_from(PropostaModel).where(
                    PropostaModel.id.in_(proposals)
                )),
                "producoes": db.scalar(select(func.count()).select_from(ProducaoModel).where(
                    ProducaoModel.orcamento_id.in_(budgets)
                )),
                "cobrancas": db.scalar(select(func.count()).select_from(CobrancaModel).where(
                    CobrancaModel.id.in_(charges)
                )),
                "pagamentos": db.scalar(select(func.count()).select_from(PagamentoModel).where(
                    PagamentoModel.id.in_(payments)
                )),
                "eventos": db.scalar(select(func.count()).select_from(ProviderWebhookEventModel).where(
                    ProviderWebhookEventModel.pagamento_id.in_(payments)
                )),
            }

    def _headers(self):
        response = self.http.post(
            "/auth/login", json={"username": self.username, "password": self.password}
        )
        self.assertEqual(response.status_code, 200)
        return {"Authorization": "Bearer " + response.json()["access_token"]}

    def _approved_fixture(self, suffix, *, objeto=None):
        email = f"{self.prefix}-{suffix}@example.com"
        public = self._browser("public", email=email)
        headers = self._headers()
        proposal = self.http.post(
            f"/orcamentos/{public['budgetId']}/proposta", headers=headers, json={}
        ).json()
        proposal = self.http.patch(
            f"/propostas/{proposal['id']}",
            headers=headers,
            json={
                "objeto": objeto or f"I2 {suffix}",
                "itens": [{"descricao": "I2 work", "quantidade": 1, "valor_unitario": "199.99"}],
                "condicoes": "I2 synthetic terms",
            },
        ).json()
        self.assertEqual(self.http.post(
            f"/propostas/{proposal['id']}/enviar", headers=headers
        ).status_code, 200)
        self.assertEqual(self.http.post(
            f"/propostas/{proposal['id']}/aprovar", headers=headers
        ).status_code, 200)
        link = self.http.get(
            f"/checkout/proposta/{proposal['id']}/link", headers=headers
        ).json()["checkout_url"]
        return public, proposal, link.rstrip("/").rsplit("/", 1)[-1], headers

    def test_connected_browser_commercial_journey(self):
        public = self._browser("public")
        budget_id = public["budgetId"]
        self._browser("admin-budget")
        headers = self._headers()
        proposal = self.http.post(f"/orcamentos/{budget_id}/proposta", headers=headers, json={}).json()
        proposal_id = proposal["id"]
        assert proposal["cliente_snapshot"]["orcamento"]["detalhes"]
        proposal = self.http.patch(f"/propostas/{proposal_id}", headers=headers, json={
            "objeto":f"I2 Connected {self.token[:8]}",
            "itens":[{"descricao":"I2 work","quantidade":1,"valor_unitario":"199.99"}],
            "condicoes":"I2 synthetic terms"}).json()
        assert self.http.get(f"/propostas/{proposal_id}/preview", headers=headers).status_code == 200
        assert self.http.post(f"/propostas/{proposal_id}/gerar-documento", headers=headers).status_code == 200
        assert self.http.post(f"/propostas/{proposal_id}/enviar", headers=headers).status_code == 200
        assert self.http.post(f"/propostas/{proposal_id}/aprovar", headers=headers).status_code == 200
        assert self.http.post(f"/propostas/{proposal_id}/aprovar", headers=headers).status_code == 200
        link = self.http.get(f"/checkout/proposta/{proposal_id}/link", headers=headers).json()["checkout_url"]
        reference = link.rstrip("/").rsplit("/", 1)[-1]
        try:
            self._browser("checkout-pix", reference=reference, option="entrada")
        except AssertionError as error:
            raise AssertionError(f"{error}\ndatabase_errors={self.db_errors}") from None
        first = next(iter(self.transport.orders))
        self.transport.change(first, "processed")
        webhook_request = "i2-" + uuid4().hex
        webhook_timestamp = str(int(time.time()))
        event = signed_webhook(self.http, first, "i2-synthetic-webhook-secret", "i2-event-first",
                               request_id=webhook_request, timestamp=webhook_timestamp)
        assert event.status_code == 200
        duplicate = signed_webhook(self.http, first, "i2-synthetic-webhook-secret", "i2-event-first",
                                   request_id=webhook_request, timestamp=webhook_timestamp)
        assert duplicate.json()["duplicate"]
        partial = self._browser("checkout-state", reference=reference)
        assert "Saldo restante" in partial["status"] and "100,00" in partial["balance"]
        self._browser("checkout-pix", reference=reference, option="saldo")
        second = next(reversed(self.transport.orders))
        self.transport.change(second, "processed")
        assert signed_webhook(self.http, second, "i2-synthetic-webhook-secret").status_code == 200
        paid = self._browser("checkout-state", reference=reference)
        assert "Pagamento confirmado" in paid["status"]
        self._browser("finance", proposal=proposal["numero"])
        with self.SessionLocal() as db:
            from models import CobrancaModel, OrcamentoModel, PagamentoModel, ProducaoModel
            assert db.scalar(select(func.count()).select_from(OrcamentoModel).where(OrcamentoModel.id == budget_id)) == 1
            assert db.scalar(select(func.count()).select_from(ProducaoModel).where(ProducaoModel.orcamento_id == budget_id)) == 1
            charge = db.query(CobrancaModel).filter_by(proposta_id=proposal_id).one()
            assert str(charge.valor_total) == "199.99" and str(charge.status) == "paga"
            assert db.scalar(select(func.count()).select_from(PagamentoModel).where(PagamentoModel.cobranca_id == charge.id)) == 2

    def test_connected_card_refund_isolation_and_invalid_tokens(self):
        public_a, proposal_a, reference_a, headers = self._approved_fixture(
            "card-a", objeto='<img src=x onerror="window.i2xss=true">I2 Card A'
        )
        _public_b, proposal_b, reference_b, _ = self._approved_fixture(
            "card-b", objeto="I2 Card B"
        )
        self.assertNotEqual(reference_a, reference_b)
        summary_a = self.http.get(f"/checkout/{reference_a}").json()
        summary_b = self.http.get(f"/checkout/{reference_b}").json()
        self.assertEqual(summary_a["proposta_numero"], proposal_a["numero"])
        self.assertEqual(summary_b["proposta_numero"], proposal_b["numero"])
        self.assertNotIn("I2 Card B", str(summary_a))
        self.assertEqual(self.http.get("/checkout/not-a-token").status_code, 422)
        self.assertEqual(
            self.http.get("/checkout/00000000-0000-0000-0000-000000000000").status_code,
            404,
        )
        self.assertEqual(
            self.http.post("/webhooks/mercado-pago", json={"data": {"id": "invalid"}}).status_code,
            401,
        )

        before = set(self.transport.orders)
        self.transport.next_status = "rejected"
        rejected = self._browser(
            "checkout-card", reference=reference_a, option="integral", expect="rejected"
        )
        self.assertTrue(rejected["rejected"])
        rejected_order = (set(self.transport.orders) - before).pop()

        before = set(self.transport.orders)
        self.transport.next_status = "action_required"
        challenge = self._browser(
            "checkout-card", reference=reference_a, option="integral", expect="action_required"
        )
        self.assertTrue(challenge["challenge"])
        challenge_order = (set(self.transport.orders) - before).pop()
        state = self._browser("checkout-state", reference=reference_a, width=390)
        self.assertIn("<img", state["description"])

        with self.SessionLocal() as db:
            from models import CobrancaModel, PagamentoModel
            charge = db.query(CobrancaModel).filter_by(proposta_id=proposal_a["id"]).one()
            payments = db.query(PagamentoModel).filter_by(cobranca_id=charge.id).all()
            self.assertEqual(len(payments), 2)
            self.assertNotIn("i2-transient-card-token", str([item.__dict__ for item in payments]))
            challenge_payment = next(item for item in payments if item.provider_order_id == challenge_order)

        self.transport.change(challenge_order, "processed")
        reconciled = self.http.post(
            f"/financeiro/pagamentos/{challenge_payment.id}/reconciliar", headers=headers
        )
        self.assertEqual(reconciled.status_code, 200)
        self.assertIn("Pagamento confirmado", self._browser(
            "checkout-state", reference=reference_a
        )["status"])

        self.transport.change(challenge_order, "refunded", "refunded")
        self.assertEqual(signed_webhook(
            self.http, challenge_order, "i2-synthetic-webhook-secret"
        ).status_code, 200)
        screenshot = str(Path(self.temp.name) / "finance-refunded.png")
        self._browser(
            "finance", proposal=proposal_a["numero"], expect="Reembolsado",
            screenshot=screenshot,
        )
        self.assertTrue(Path(screenshot).is_file())
        refunded = self.http.get(f"/checkout/{reference_a}").json()
        self.assertEqual(refunded["valor_pago"], "0.00")
        self.assertEqual(refunded["saldo"], "199.99")
        self.assertNotEqual(rejected_order, challenge_order)
        self.assertEqual(public_a["url"].split("?")[0].endswith("calculadora.html"), True)

        before = set(self.transport.orders)
        self._browser("checkout-pix", reference=reference_b, option="integral")
        mismatch_order = (set(self.transport.orders) - before).pop()
        self.transport.orders[mismatch_order]["transactions"]["payments"][0]["amount"] = "0.01"
        mismatch = signed_webhook(
            self.http, mismatch_order, "i2-synthetic-webhook-secret"
        )
        self.assertEqual(mismatch.status_code, 200)
        self.assertEqual(mismatch.json()["status"], "conflict")
        with self.SessionLocal() as db:
            from models import CobrancaModel, PagamentoModel
            charge_b = db.query(CobrancaModel).filter_by(proposta_id=proposal_b["id"]).one()
            payment_b = db.query(PagamentoModel).filter_by(cobranca_id=charge_b.id).one()
            self.assertEqual(charge_b.status, "pendente")
            self.assertEqual(payment_b.reconciliation_status, "conflict")

    def test_concurrent_budget_retry_has_one_effect(self):
        for iteration in range(5):
            key = str(uuid4())
            payload = {"nome_cliente":self.name, "email":f"{self.prefix}-race@example.com",
                       "servico":"I2 concurrency", "valor_total":199.99,
                       "detalhes":f"I2 race {iteration}"}
            with ThreadPoolExecutor(max_workers=2) as pool:
                responses = list(pool.map(lambda _: httpx.post(self.server + "/orcamentos", json=payload,
                    headers={"Idempotency-Key":key}, timeout=40), range(2)))
            assert {response.status_code for response in responses} == {200}
            assert len({response.json()["id"] for response in responses}) == 1
        with self.SessionLocal() as db:
            from models import OrcamentoModel
            assert db.scalar(select(func.count()).select_from(OrcamentoModel).where(OrcamentoModel.email == f"{self.prefix}-race@example.com")) == 5
