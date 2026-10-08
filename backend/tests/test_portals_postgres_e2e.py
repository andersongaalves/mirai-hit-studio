"""Opt-in Portals E2E against an isolated PostgreSQL 17 database."""

from __future__ import annotations

import json
import os
import subprocess
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import httpx
from alembic.config import Config
from alembic.script import ScriptDirectory
from commercial_i2_support import local_frontend_server, local_server
from services.producao_arquivo_storage import ProducaoArquivoStorageError
from sqlalchemy import delete, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

POSTGRES_URL = os.getenv("MIRAI_PORTALS_E2E_DATABASE_URL", "")
ACK = os.getenv("MIRAI_PORTALS_E2E_ALLOW", "")
REQUIRED_ACK = "POSTGRES_17_DISPOSABLE_ONLY"


class MemoryStorage:
    """Verifiable boundary fake; application authorization remains real."""

    def __init__(self):
        self.objects = {}
        self.deleted = []
        self.counter = 0
        self.namespace = uuid.uuid4().hex

    def clear(self):
        self.objects.clear()
        self.deleted.clear()
        self.counter = 0
        self.namespace = uuid.uuid4().hex

    def save(self, data, mime_type):
        self.counter += 1
        key = f"arquivos/{self.namespace}/{self.counter:032x}"
        self.objects[key] = {"data": bytes(data), "mime_type": mime_type}
        return key

    def read(self, key):
        try:
            return self.objects[key]["data"]
        except KeyError:
            raise ProducaoArquivoStorageError("Arquivo sintetico ausente.") from None

    def delete(self, key):
        self.deleted.append(key)
        self.objects.pop(key, None)


class FailingStorage(MemoryStorage):
    def save(self, data, mime_type):
        raise ProducaoArquivoStorageError("Falha sintetica de Storage.")


@unittest.skipUnless(
    bool(POSTGRES_URL) and ACK == REQUIRED_ACK,
    "set MIRAI_PORTALS_E2E_DATABASE_URL and acknowledge the disposable PostgreSQL 17 database",
)
class PortalsPostgreSQLE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configured = make_url(POSTGRES_URL)
        if not configured.drivername.startswith("postgresql"):
            raise RuntimeError("Portals E2E requires PostgreSQL")
        if configured.host not in {"127.0.0.1", "localhost"}:
            raise RuntimeError("Portals E2E refuses a non-loopback database")
        if "portals_e2e" not in (configured.database or ""):
            raise RuntimeError("Portals E2E requires a clearly disposable database name")

        cls.proposal_pdf_directory = TemporaryDirectory(prefix="mirai-proposal-e2e-")
        cls.previous_proposal_pdf_dir = os.environ.get("PROPOSTA_PDF_DIR")
        os.environ["PROPOSTA_PDF_DIR"] = cls.proposal_pdf_directory.name

        from core.config import settings
        from database import SessionLocal, engine
        from main import app
        from services import producao_arquivo_service

        actual = make_url(str(engine.url))
        def target(url):
            return url.drivername, url.host, url.port, url.database

        if target(actual) != target(configured):
            raise RuntimeError("Application database differs from the authorized E2E target")

        with engine.connect() as connection:
            major = int(connection.execute(text("SHOW server_version_num")).scalar_one()) // 10000
            if major != 17:
                raise RuntimeError("Portals E2E requires PostgreSQL 17")
            current = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        alembic = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        head = ScriptDirectory.from_config(alembic).get_current_head()
        if not head or current != head:
            raise RuntimeError("Portals E2E database is not at the single Alembic head")

        cls.engine = engine
        cls.SessionLocal = SessionLocal
        cls.app = app
        cls.storage = MemoryStorage()
        settings.PUBLIC_FRONTEND_URL = "http://localhost:4173"

        cls.stack = ExitStack()
        cls.stack.enter_context(
            patch.object(
                producao_arquivo_service,
                "new_production_file_storage",
                return_value=cls.storage,
            )
        )
        cls.stack.enter_context(
            patch("core.http_security.allow_request", return_value=(True, 0))
        )
        cls._cleanup()
        cls.api_url = cls.stack.enter_context(local_server(app, port=8000))
        frontend = Path(__file__).resolve().parents[2] / "frontend"
        cls.frontend_url = cls.stack.enter_context(
            local_frontend_server(frontend, port=4173)
        )
        cls.http = cls.stack.enter_context(
            httpx.Client(base_url=cls.api_url, timeout=30, trust_env=False)
        )

    @classmethod
    def tearDownClass(cls):
        try:
            cls._cleanup()
            cls.storage.clear()
        finally:
            cls.stack.close()
            cls.engine.dispose()
            if cls.previous_proposal_pdf_dir is None:
                os.environ.pop("PROPOSTA_PDF_DIR", None)
            else:
                os.environ["PROPOSTA_PDF_DIR"] = cls.previous_proposal_pdf_dir
            cls.proposal_pdf_directory.cleanup()

    def setUp(self):
        self._cleanup()
        self.storage.clear()
        self.ids = self._seed()

    def tearDown(self):
        self._cleanup()
        self.storage.clear()

    @classmethod
    def _cleanup(cls):
        from models import (
            AuditLogModel,
            AuthRateLimitModel,
            ClienteAcessoModel,
            ClienteModel,
            CobrancaModel,
            ConfigModel,
            OrcamentoModel,
            PagamentoModel,
            ProducaoArquivoModel,
            ProducaoModel,
            PropostaModel,
            RepasseProdutorModel,
            ServicoModel,
            UsuarioModel,
        )

        with cls.SessionLocal.begin() as db:
            for model in (
                AuditLogModel,
                AuthRateLimitModel,
                ClienteAcessoModel,
                RepasseProdutorModel,
                ProducaoArquivoModel,
                PagamentoModel,
                CobrancaModel,
                ProducaoModel,
                PropostaModel,
                OrcamentoModel,
                UsuarioModel,
                ClienteModel,
                ServicoModel,
                ConfigModel,
            ):
                db.execute(delete(model))

    def _seed(self):
        from core.security import get_password_hash
        from models import (
            ClienteModel,
            CobrancaModel,
            ConfigModel,
            OrcamentoModel,
            PagamentoModel,
            ProducaoModel,
            PropostaModel,
            ServicoModel,
            UsuarioModel,
        )
        from services.documento_storage import LocalDocumentoStorage

        password = "Portals-E2E-only!"
        with self.SessionLocal.begin() as db:
            db.add(ConfigModel(id=1))
            client_a = ClienteModel(nome="E2E Cliente A", email="client-a@example.com")
            client_b = ClienteModel(nome="E2E Cliente B", email="client-b@example.com")
            provision = ClienteModel(nome="E2E Provision", email="provision@example.com")
            db.add_all([client_a, client_b, provision])
            db.flush()
            admin = UsuarioModel(
                username="e2e-admin",
                password_hash=get_password_hash(password),
                role="admin",
                is_admin=True,
                ativo=True,
            )
            producer_a = UsuarioModel(
                username="e2e-producer-a",
                password_hash=get_password_hash(password),
                role="produtor",
                is_admin=False,
                ativo=True,
            )
            producer_b = UsuarioModel(
                username="e2e-producer-b",
                password_hash=get_password_hash(password),
                role="produtor",
                is_admin=False,
                ativo=True,
            )
            client_user_a = UsuarioModel(
                username="e2e-client-a",
                password_hash=get_password_hash(password),
                role="cliente",
                is_admin=False,
                ativo=True,
                cliente_id=client_a.id,
            )
            client_user_b = UsuarioModel(
                username="e2e-client-b",
                password_hash=get_password_hash(password),
                role="cliente",
                is_admin=False,
                ativo=True,
                cliente_id=client_b.id,
            )
            db.add_all([admin, producer_a, producer_b, client_user_a, client_user_b])
            db.add(
                ServicoModel(
                    nome="E2E Mixagem",
                    subtitulo="Servico sintetico",
                    valor_base=1000.0,
                    categoria="avulso",
                    parametros="",
                )
            )
            db.flush()
            flow_budget = OrcamentoModel(
                nome_cliente=client_a.nome,
                email=client_a.email,
                servico="Mixagem",
                cliente_id=client_a.id,
            )
            other_budget = OrcamentoModel(
                nome_cliente=client_b.nome,
                email=client_b.email,
                servico="Masterizacao",
                cliente_id=client_b.id,
                produtor_id=producer_b.id,
            )
            completed_budget = OrcamentoModel(
                nome_cliente=client_a.nome,
                email=client_a.email,
                servico="Producao",
                cliente_id=client_a.id,
                produtor_id=producer_a.id,
            )
            invite_budget = OrcamentoModel(
                nome_cliente=provision.nome,
                email=provision.email,
                servico="Mixagem",
                cliente_id=provision.id,
                status="aprovado",
            )
            client_proposal_budget = OrcamentoModel(
                nome_cliente=client_a.nome,
                email=client_a.email,
                servico="Produção musical",
                cliente_id=client_a.id,
                valor_total=1200.0,
                status="proposta_enviada",
            )
            other_proposal_budget = OrcamentoModel(
                nome_cliente=client_b.nome,
                email=client_b.email,
                servico="Mixagem",
                cliente_id=client_b.id,
                valor_total=800.0,
                status="proposta_enviada",
            )
            db.add_all([
                flow_budget,
                other_budget,
                completed_budget,
                invite_budget,
                client_proposal_budget,
                other_proposal_budget,
            ])
            db.flush()
            proposal = PropostaModel(
                orcamento_id=flow_budget.id,
                numero="E2E-PROP-001",
                status="aceita",
                cliente_snapshot={},
                itens_json=[],
                pagamentos_json=[],
                totais_json={},
            )
            db.add(proposal)
            db.flush()
            invite_proposal = PropostaModel(
                orcamento_id=invite_budget.id,
                numero="E2E-PROP-INVITE",
                status="aceita",
                cliente_snapshot={
                    "cliente": {
                        "nome": provision.nome,
                        "email": provision.email,
                        "whatsapp": None,
                    },
                    "orcamento": {
                        "id": invite_budget.id,
                        "servico": invite_budget.servico,
                        "detalhes": None,
                        "valor_total": None,
                        "link_guia": None,
                    },
                },
                itens_json=[],
                pagamentos_json=[],
                totais_json={},
                aprovada_em=datetime.now(timezone.utc),
            )
            db.add(invite_proposal)
            db.flush()
            sent_at = datetime.now(timezone.utc)
            client_proposal = PropostaModel(
                orcamento_id=client_proposal_budget.id,
                numero="E2E-PROP-CLIENT-001",
                status="enviada",
                cliente_snapshot={
                    "cliente": {
                        "nome": client_a.nome,
                        "email": client_a.email,
                        "whatsapp": None,
                    },
                    "orcamento": {
                        "id": client_proposal_budget.id,
                        "servico": client_proposal_budget.servico,
                        "detalhes": None,
                        "valor_total": "1200.00",
                        "link_guia": None,
                    },
                },
                objeto="Produção musical E2E",
                descricao="Proposta sintética do Portal do Cliente.",
                itens_json=[{
                    "descricao": "Produção musical",
                    "quantidade": "1",
                    "valor_unitario": "1200.00",
                    "desconto": "0.00",
                }],
                pagamentos_json=[],
                politica_pagamento="entrada_50_50",
                condicoes="Entrada de 50% para início.",
                totais_json={
                    "subtotal": "1200.00",
                    "desconto": "0.00",
                    "total": "1200.00",
                },
                enviada_em=sent_at,
            )
            other_client_proposal = PropostaModel(
                orcamento_id=other_proposal_budget.id,
                numero="E2E-PROP-CLIENT-002",
                status="enviada",
                cliente_snapshot={
                    "cliente": {
                        "nome": client_b.nome,
                        "email": client_b.email,
                        "whatsapp": None,
                    },
                    "orcamento": {
                        "id": other_proposal_budget.id,
                        "servico": other_proposal_budget.servico,
                        "detalhes": None,
                        "valor_total": "800.00",
                        "link_guia": None,
                    },
                },
                objeto="Mixagem E2E",
                descricao="Proposta sintética alheia.",
                itens_json=[{
                    "descricao": "Mixagem",
                    "quantidade": "1",
                    "valor_unitario": "800.00",
                    "desconto": "0.00",
                }],
                pagamentos_json=[],
                politica_pagamento="integral",
                condicoes="Pagamento integral.",
                totais_json={
                    "subtotal": "800.00",
                    "desconto": "0.00",
                    "total": "800.00",
                },
                enviada_em=sent_at,
            )
            db.add_all([client_proposal, other_client_proposal])
            db.flush()
            pdf = b"%PDF-1.4\n% synthetic client proposal\n%%EOF\n"
            client_proposal.pdf_path = LocalDocumentoStorage().salvar(
                pdf,
                client_proposal.id,
                client_proposal.versao,
            )
            client_proposal.pdf_sha256 = sha256(pdf).hexdigest()
            client_proposal.gerada_em = sent_at
            charge = CobrancaModel(
                proposta_id=proposal.id,
                cliente_id=client_a.id,
                valor_total=Decimal("1000.00"),
                moeda="BRL",
                status="parcialmente_paga",
                referencia_externa="00000000-0000-4000-8000-000000000001",
            )
            db.add(charge)
            db.flush()
            db.add(
                PagamentoModel(
                    cobranca_id=charge.id,
                    tipo="entrada",
                    valor=Decimal("400.00"),
                    status="aprovado",
                    metodo="pix",
                    provider="synthetic",
                    provider_order_id="E2E-PAY-001",
                )
            )
            other_production = ProducaoModel(
                titulo="E2E Faixa B",
                cliente=client_b.nome,
                servico="Masterizacao",
                status="em_producao",
                produtor_id=producer_b.id,
                orcamento_id=other_budget.id,
                etapas="[]",
            )
            completed = ProducaoModel(
                titulo="E2E Historico A",
                cliente=client_a.nome,
                servico="Producao",
                status="entregue",
                produtor_id=producer_a.id,
                orcamento_id=completed_budget.id,
                etapas="[]",
            )
            db.add_all([other_production, completed])
            db.flush()
            return {
                "password": password,
                "admin_id": admin.id,
                "producer_a_id": producer_a.id,
                "producer_b_id": producer_b.id,
                "client_user_a_id": client_user_a.id,
                "client_a_id": client_a.id,
                "client_b_id": client_b.id,
                "provision_client_id": provision.id,
                "flow_budget_id": flow_budget.id,
                "invite_proposal_id": invite_proposal.id,
                "client_proposal_id": client_proposal.id,
                "client_proposal_version": client_proposal.versao,
                "other_client_proposal_id": other_client_proposal.id,
                "other_production_id": other_production.id,
                "completed_production_id": completed.id,
            }

    def test_client_invite_postgresql17_concurrency_and_activation(self):
        from models import ClienteAcessoModel, UsuarioModel
        from services.email_service import EmailService

        admin = self._login("e2e-admin")
        path = f"/propostas/{self.ids['invite_proposal_id']}/acesso-cliente/convidar"
        with patch.object(
            EmailService,
            "enviar_convite_cliente",
            return_value={"id": "postgres-e2e-invite"},
        ) as email:
            def send(_):
                with httpx.Client(base_url=self.api_url, timeout=30, trust_env=False) as client:
                    return client.post(path, headers=admin).status_code

            with ThreadPoolExecutor(max_workers=2) as executor:
                statuses = sorted(executor.map(send, range(2)))

        self.assertEqual(statuses, [200, 409])
        self.assertEqual(email.call_count, 1)
        token = parse_qs(urlparse(email.call_args.args[1]).query)["token"][0]
        with self.SessionLocal() as db:
            rows = db.query(ClienteAcessoModel).all()
            self.assertEqual(len(rows), 1)
            self.assertNotEqual(rows[0].token_hash, token)

        validated = self.http.post("/cliente-acessos/validar", json={"token": token})
        self.assertEqual(validated.status_code, 200, validated.text)
        self.assertEqual(validated.json()["estado"], "valido")
        activated = self.http.post("/cliente-acessos/ativar", json={
            "token": token,
            "username": "e2e-invited-client",
            "password": self.ids["password"],
        })
        self.assertEqual(activated.status_code, 200, activated.text)
        login = self._login("e2e-invited-client")
        self.assertTrue(login["Authorization"].startswith("Bearer "))
        with self.SessionLocal() as db:
            user = db.scalar(select(UsuarioModel).where(UsuarioModel.username == "e2e-invited-client"))
            self.assertEqual(user.cliente_id, self.ids["provision_client_id"])
            self.assertEqual(user.role, "cliente")
            self.assertFalse(user.is_admin)
            access = db.query(ClienteAcessoModel).one()
            self.assertEqual(access.usuario_id, user.id)
            self.assertIsNotNone(access.token_consumed_at)

    def test_public_signup_postgresql17_concurrency_and_takeover_protection(self):
        from models import ClienteAcessoModel, ClienteModel, UsuarioModel
        from services.email_service import EmailService

        payload = {
            "nome": "E2E Public Signup",
            "email": "public-signup@example.com",
            "telefone": "11977770101",
            "privacy_accepted": True,
        }
        with patch.object(
            EmailService,
            "enviar_confirmacao_cadastro",
            return_value={"id": "postgres-e2e-signup"},
        ) as email:
            def send(_):
                with httpx.Client(base_url=self.api_url, timeout=30, trust_env=False) as client:
                    response = client.post("/auth/client-signup", json=payload)
                    return response.status_code, response.json()

            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(send, range(2)))

        self.assertEqual([item[0] for item in results], [202, 202])
        self.assertEqual(results[0][1], results[1][1])
        self.assertEqual(email.call_count, 1)
        old_token = parse_qs(urlparse(email.call_args.args[1]).query)["token"][0]
        with self.SessionLocal() as db:
            access = db.scalar(
                select(ClienteAcessoModel).where(
                    ClienteAcessoModel.email_normalizado == payload["email"]
                )
            )
            self.assertIsNotNone(access)
            self.assertEqual(access.origem, "public_signup")
            self.assertEqual(access.token_finalidade, "verificacao")
            self.assertNotEqual(access.token_hash, old_token)
            signup_client_id = access.cliente_id
            self.assertEqual(
                db.query(ClienteModel).filter(ClienteModel.email == payload["email"]).count(),
                1,
            )

        invalid = self.http.post("/auth/client-signup", json={
            **payload,
            "email": "not-an-email",
            "role": "admin",
            "is_admin": True,
        })
        self.assertEqual(invalid.status_code, 422)
        with patch.object(
            EmailService,
            "enviar_confirmacao_cadastro",
            return_value={"id": "postgres-e2e-signup-resend"},
        ) as resent:
            resend = self.http.post(
                "/auth/client-signup/resend",
                json={"email": payload["email"]},
            )
        self.assertEqual(resend.status_code, 202, resend.text)
        token = parse_qs(urlparse(resent.call_args.args[1]).query)["token"][0]
        self.assertNotEqual(token, old_token)
        self.assertEqual(
            self.http.post(
                "/cliente-acessos/validar",
                json={"token": old_token},
            ).status_code,
            422,
        )

        def activate(_):
            with httpx.Client(base_url=self.api_url, timeout=30, trust_env=False) as client:
                return client.post("/cliente-acessos/ativar", json={
                    "token": token,
                    "username": "e2e-public-client",
                    "password": self.ids["password"],
                }).status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = sorted(executor.map(activate, range(2)))
        self.assertEqual(statuses, [200, 409])

        with self.SessionLocal() as db:
            user = db.scalar(
                select(UsuarioModel).where(UsuarioModel.username == "e2e-public-client")
            )
            self.assertEqual(user.cliente_id, signup_client_id)
            self.assertEqual(user.role, "cliente")
            self.assertFalse(user.is_admin)

        before_clients = None
        with self.SessionLocal() as db:
            before_clients = db.query(ClienteModel).count()
            commercial = db.get(ClienteModel, self.ids["client_a_id"])
            commercial_email = commercial.email
        with patch.object(EmailService, "enviar_confirmacao_cadastro") as blocked_email:
            blocked = self.http.post("/auth/client-signup", json={
                **payload,
                "email": commercial_email,
                "telefone": None,
            })
        self.assertEqual(blocked.status_code, 202, blocked.text)
        self.assertEqual(blocked.json(), results[0][1])
        self.assertEqual(blocked_email.call_count, 0)
        with self.SessionLocal() as db:
            self.assertEqual(db.query(ClienteModel).count(), before_clients)
            commercial_user = db.scalar(
                select(UsuarioModel).where(UsuarioModel.cliente_id == self.ids["client_a_id"])
            )
            self.assertEqual(commercial_user.username, "e2e-client-a")

    def test_browser_public_signup_uses_real_backend_and_postgresql(self):
        from models import ClienteAcessoModel, ClienteModel, UsuarioModel
        from services.email_service import EmailService

        root = Path(__file__).resolve().parents[2]
        with TemporaryDirectory(prefix="mirai-signup-e2e-") as directory:
            activation_file = Path(directory) / "activation-url.txt"

            def capture_email(_client, activation_url, *, idempotency_key):
                self.assertTrue(idempotency_key.startswith("client-signup/"))
                activation_file.write_text(activation_url, encoding="utf-8")
                return {"id": "browser-signup-message"}

            env = {
                **os.environ,
                "E2E_PASSWORD": self.ids["password"],
                "E2E_SIGNUP_ACTIVATION_FILE": str(activation_file),
            }
            with patch.object(
                EmailService,
                "enviar_confirmacao_cadastro",
                side_effect=capture_email,
            ):
                result = subprocess.run(
                    [
                        os.getenv("NODE_BINARY", "node"),
                        str(root / "frontend/tests/client_signup_postgres_e2e.cjs"),
                    ],
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=180,
                    check=False,
                )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("CLIENT_SIGNUP_E2E_PASS", result.stdout)
        with self.SessionLocal() as db:
            client = db.scalar(
                select(ClienteModel).where(
                    ClienteModel.email == "browser-signup@example.com"
                )
            )
            user = db.scalar(select(UsuarioModel).where(UsuarioModel.cliente_id == client.id))
            access = db.scalar(
                select(ClienteAcessoModel).where(ClienteAcessoModel.cliente_id == client.id)
            )
            self.assertEqual(user.role, "cliente")
            self.assertFalse(user.is_admin)
            self.assertIsNotNone(access.token_consumed_at)
            self.assertEqual(client.orcamentos, [])

    def _seed_recovery_access(self):
        from models import ClienteAcessoModel, UsuarioModel

        now = datetime.now(timezone.utc)
        with self.SessionLocal.begin() as db:
            user = db.scalar(
                select(UsuarioModel).where(
                    UsuarioModel.cliente_id == self.ids["client_a_id"]
                )
            )
            db.add(
                ClienteAcessoModel(
                    cliente_id=self.ids["client_a_id"],
                    usuario_id=user.id,
                    email_normalizado="client-a@example.com",
                    origem="public_signup",
                    token_finalidade="verificacao",
                    token_hash="9" * 64,
                    token_expires_at=now + timedelta(hours=1),
                    token_consumed_at=now,
                    email_verified_at=now,
                    last_sent_at=now,
                    privacy_accepted_at=now,
                    send_count=1,
                )
            )

    def test_password_recovery_postgresql17_concurrency_and_revocation(self):
        from models import AuditLogModel, ClienteAcessoModel, UsuarioModel
        from services.email_service import EmailService

        self._seed_recovery_access()
        client_a = self._login("e2e-client-a")
        client_b = self._login("e2e-client-b")
        admin = self._login("e2e-admin")
        producer = self._login("e2e-producer-a")

        with patch.object(
            EmailService,
            "enviar_recuperacao_senha",
            return_value={"id": "postgres-e2e-recovery"},
        ) as email:
            requested = self.http.post(
                "/auth/password-recovery",
                json={"email": "client-a@example.com"},
            )
        self.assertEqual(requested.status_code, 202, requested.text)
        token = parse_qs(urlparse(email.call_args.args[1]).query)["token"][0]
        old_session = dict(client_a)

        def reset(_):
            with httpx.Client(base_url=self.api_url, timeout=30, trust_env=False) as client:
                return client.post(
                    "/auth/password-recovery/reset",
                    json={"token": token, "password": "New-Recovery-E2E!"},
                ).status_code

        def concurrent_session(_):
            with httpx.Client(base_url=self.api_url, timeout=30, trust_env=False) as client:
                return client.get("/auth/me", headers=old_session).status_code

        with ThreadPoolExecutor(max_workers=3) as executor:
            reset_futures = [executor.submit(reset, index) for index in range(2)]
            session_future = executor.submit(concurrent_session, 0)
            reset_results = [future.result() for future in reset_futures]
            concurrent_status = session_future.result()
        self.assertEqual(sorted(reset_results), [200, 409])
        self.assertIn(concurrent_status, {200, 401})
        self.assertEqual(self.http.get("/auth/me", headers=old_session).status_code, 401)
        self.assertEqual(self.http.get("/auth/me", headers=admin).status_code, 200)
        self.assertEqual(self.http.get("/auth/me", headers=producer).status_code, 200)
        self.assertEqual(self.http.get("/auth/me", headers=client_b).status_code, 200)
        self.assertEqual(
            self.http.post(
                "/auth/login",
                json={"username": "e2e-client-a", "password": self.ids["password"]},
            ).status_code,
            401,
        )
        self.assertEqual(
            self.http.post(
                "/auth/login",
                json={"username": "e2e-client-a", "password": "New-Recovery-E2E!"},
            ).status_code,
            200,
        )
        self.assertEqual(
            self.http.post(
                "/auth/password-recovery/reset",
                json={"token": token, "password": "Replay-Recovery-E2E!"},
            ).status_code,
            409,
        )

        with self.SessionLocal() as db:
            user = db.scalar(
                select(UsuarioModel).where(UsuarioModel.username == "e2e-client-a")
            )
            access = db.query(ClienteAcessoModel).one()
            self.assertEqual(user.auth_version, 1)
            self.assertIsNotNone(access.token_consumed_at)
            self.assertEqual(
                db.query(AuditLogModel).filter_by(
                    action="client_access.password_reset_completed"
                ).count(),
                1,
            )

        with patch.object(
            EmailService,
            "enviar_recuperacao_senha",
            side_effect=RuntimeError("private-provider-error"),
        ):
            failed_delivery = self.http.post(
                "/auth/password-recovery",
                json={"email": "client-a@example.com"},
            )
        self.assertEqual(failed_delivery.status_code, 202, failed_delivery.text)

    def test_browser_password_recovery_uses_real_backend_and_postgresql(self):
        from services.email_service import EmailService

        self._seed_recovery_access()
        root = Path(__file__).resolve().parents[2]
        with TemporaryDirectory(prefix="mirai-recovery-e2e-") as directory:
            recovery_file = Path(directory) / "recovery-url.txt"

            def capture_email(_client, recovery_url, *, idempotency_key):
                self.assertTrue(idempotency_key.startswith("client-recovery/"))
                recovery_file.write_text(recovery_url, encoding="utf-8")
                return {"id": "browser-recovery-message"}

            env = {
                **os.environ,
                "E2E_RECOVERY_URL_FILE": str(recovery_file),
                "E2E_RECOVERY_USERNAME": "e2e-client-a",
                "E2E_RECOVERY_EMAIL": "client-a@example.com",
                "E2E_OLD_PASSWORD": self.ids["password"],
                "E2E_NEW_PASSWORD": "Browser-Recovery-E2E!",
            }
            with patch.object(
                EmailService,
                "enviar_recuperacao_senha",
                side_effect=capture_email,
            ):
                result = subprocess.run(
                    [
                        os.getenv("NODE_BINARY", "node"),
                        str(root / "frontend/tests/password_recovery_postgres_e2e.cjs"),
                    ],
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=180,
                    check=False,
                )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASSWORD_RECOVERY_POSTGRES_E2E_PASS", result.stdout)

    def _login(self, username):
        response = self.http.post(
            "/auth/login",
            json={"username": username, "password": self.ids["password"]},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return {"Authorization": "Bearer " + response.json()["access_token"]}

    def _create_flow_production(self, admin):
        assigned = self.http.patch(
            f"/orcamentos/{self.ids['flow_budget_id']}/produtor",
            headers=admin,
            json={"produtor_id": self.ids["producer_a_id"]},
        )
        self.assertEqual(assigned.status_code, 200, assigned.text)
        created = self.http.post(
            "/producoes",
            headers=admin,
            json={
                "titulo": "E2E Faixa Integrada",
                "cliente": "E2E Cliente A",
                "servico": "Mixagem",
                "observacoes": "interno e nunca exposto",
                "etapas": json.dumps([{"nome": "Producao", "feito": False}]),
                "produtor_id": self.ids["producer_a_id"],
                "orcamento_id": self.ids["flow_budget_id"],
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        return created.json()["id"]

    def test_client_proposal_acceptance_postgresql17_concurrency(self):
        from core.config import settings
        from models import (
            AuditLogModel,
            CobrancaModel,
            ProducaoModel,
            PropostaModel,
            UsuarioModel,
        )
        from services import portal_cliente_proposta_service

        previous = settings.COMMERCIAL_PIPELINE_V2_ENABLED
        settings.COMMERCIAL_PIPELINE_V2_ENABLED = True
        try:
            admin = self._login("e2e-admin")
            producer = self._login("e2e-producer-a")
            client = self._login("e2e-client-a")
            own_id = self.ids["client_proposal_id"]
            other_id = self.ids["other_client_proposal_id"]

            self.assertEqual(
                self.http.get("/portal/cliente/propostas", headers=admin).status_code,
                403,
            )
            self.assertEqual(
                self.http.get("/portal/cliente/propostas", headers=producer).status_code,
                403,
            )
            own = self.http.get(f"/portal/cliente/propostas/{own_id}", headers=client)
            self.assertEqual(own.status_code, 200, own.text)
            self.assertEqual(own.json()["status"], "enviada")
            self.assertEqual(
                self.http.get(f"/portal/cliente/propostas/{other_id}", headers=client).status_code,
                404,
            )
            self.assertEqual(
                self.http.get(
                    f"/portal/cliente/propostas/{other_id}/documento",
                    headers=client,
                ).status_code,
                404,
            )
            document = self.http.get(
                f"/portal/cliente/propostas/{own_id}/documento",
                headers=client,
            )
            self.assertEqual(document.status_code, 200, document.text)
            self.assertTrue(document.content.startswith(b"%PDF-"))
            self.assertEqual(document.headers["cache-control"], "private, no-store")

            gate = Barrier(2)

            def accept(request_id):
                with self.SessionLocal() as db:
                    actor = db.get(UsuarioModel, self.ids["client_user_a_id"])
                    gate.wait(timeout=10)
                    return portal_cliente_proposta_service.accept(
                        db,
                        own_id,
                        self.ids["client_a_id"],
                        self.ids["client_proposal_version"],
                        actor,
                        request_id,
                    )

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(accept, ("accept-a", "accept-b")))
            self.assertEqual([item["status"] for item in results], ["aceita", "aceita"])

            with self.SessionLocal() as db:
                proposal = db.get(PropostaModel, own_id)
                self.assertEqual(proposal.status, "aceita")
                self.assertEqual(
                    db.query(CobrancaModel).filter(CobrancaModel.proposta_id == own_id).count(),
                    1,
                )
                self.assertEqual(
                    db.query(ProducaoModel)
                    .filter(ProducaoModel.orcamento_id == proposal.orcamento_id)
                    .count(),
                    0,
                )
                self.assertEqual(
                    db.query(AuditLogModel)
                    .filter(AuditLogModel.action == "proposal.accepted_by_client")
                    .count(),
                    1,
                )

            refused = self.http.post(
                f"/portal/cliente/propostas/{own_id}/recusar",
                headers=client,
                json={"versao": self.ids["client_proposal_version"]},
            )
            self.assertEqual(refused.status_code, 409, refused.text)
        finally:
            settings.COMMERCIAL_PIPELINE_V2_ENABLED = previous

    def test_backend_postgresql17_matrix(self):
        from core.config import settings
        from jose import jwt
        from models import (
            AuditLogModel,
            ProducaoArquivoModel,
            ProducaoModel,
            RepasseProdutorModel,
            UsuarioModel,
        )
        from services import producao_arquivo_service

        self.assertEqual(self.http.get("/portal/produtor/producoes").status_code, 401)
        self.assertEqual(self.http.get("/portal/cliente/producoes").status_code, 401)
        admin = self._login("e2e-admin")
        producer_a = self._login("e2e-producer-a")
        producer_b = self._login("e2e-producer-b")
        client_a = self._login("e2e-client-a")
        client_b = self._login("e2e-client-b")
        production_id = self._create_flow_production(admin)

        self.assertEqual(
            self.http.get(f"/portal/produtor/producoes/{production_id}", headers=producer_b).status_code,
            404,
        )
        self.assertEqual(
            self.http.get(f"/portal/cliente/producoes/{production_id}", headers=client_b).status_code,
            404,
        )
        own = self.http.get(f"/portal/cliente/producoes/{production_id}", headers=client_a)
        self.assertEqual(own.status_code, 200, own.text)
        self.assertNotIn("observacoes", own.json())

        for status in ("em_producao", "revisao", "em_producao"):
            changed = self.http.patch(
                f"/portal/produtor/producoes/{production_id}/status",
                headers=producer_a,
                json={"status": status},
            )
            self.assertEqual(changed.status_code, 200, changed.text)
        blocked = self.http.patch(
            f"/portal/produtor/producoes/{production_id}/status",
            headers=producer_a,
            json={"status": "entregue"},
        )
        self.assertEqual(blocked.status_code, 409)

        material = self.http.post(
            f"/portal/cliente/producoes/{production_id}/arquivos",
            headers=client_a,
            data={"tipo": "material"},
            files={"arquivo": ("voice.wav", b"RIFF-e2e-client", "audio/wav")},
        )
        self.assertEqual(material.status_code, 201, material.text)
        self.assertNotIn("object_key", material.json())
        self.assertEqual(
            self.http.get(
                f"/portal/produtor/producoes/{production_id}/arquivos",
                headers=producer_a,
            ).status_code,
            200,
        )
        preview = self.http.post(
            f"/portal/produtor/producoes/{production_id}/arquivos",
            headers=producer_a,
            data={"tipo": "previa"},
            files={"arquivo": ("preview.mp3", b"ID3-e2e-preview", "audio/mpeg")},
        )
        self.assertEqual(preview.status_code, 201, preview.text)
        visible = self.http.patch(
            f"/producoes/{production_id}/arquivos/{preview.json()['id']}/visibilidade",
            headers=admin,
            json={"visivel_produtor": True, "visivel_cliente": True},
        )
        self.assertEqual(visible.status_code, 200, visible.text)
        client_download = self.http.get(
            f"/portal/cliente/arquivos/{preview.json()['id']}/conteudo",
            headers=client_a,
        )
        self.assertEqual(client_download.content, b"ID3-e2e-preview")
        self.assertEqual(client_download.headers["cache-control"], "private, no-store")

        hidden = self.http.post(
            f"/producoes/{production_id}/arquivos",
            headers=admin,
            data={"tipo": "referencia", "visivel_produtor": "true", "visivel_cliente": "false"},
            files={"arquivo": ("internal.pdf", b"%PDF-internal", "application/pdf")},
        )
        self.assertEqual(hidden.status_code, 201, hidden.text)
        self.assertEqual(
            self.http.get(
                f"/portal/cliente/arquivos/{hidden.json()['id']}/conteudo",
                headers=client_a,
            ).status_code,
            404,
        )

        payout = self.http.put(
            f"/producoes/{production_id}/repasse",
            headers=admin,
            json={"valor_combinado": "137.45"},
        )
        self.assertEqual(payout.status_code, 200, payout.text)
        self.assertEqual(payout.json()["valor_combinado"], "137.45")
        self.assertEqual(
            self.http.put(
                f"/producoes/{production_id}/repasse",
                headers=producer_a,
                json={"valor_combinado": "999.00"},
            ).status_code,
            403,
        )
        self.assertEqual(self.http.get("/portal/produtor/repasses", headers=client_a).status_code, 403)
        self.assertEqual(
            self.http.post(f"/producoes/{production_id}/repasse/liberar", headers=admin).status_code,
            200,
        )
        paid = self.http.post(
            f"/producoes/{production_id}/repasse/pagar",
            headers=admin,
            json={"referencia_pagamento": "E2E-PIX-SYNTHETIC"},
        )
        self.assertEqual(paid.status_code, 200, paid.text)
        self.assertEqual(paid.json()["status"], "pago")

        with self.SessionLocal.begin() as db:
            stored = db.scalar(
                select(RepasseProdutorModel).where(RepasseProdutorModel.producao_id == production_id)
            )
            self.assertEqual(stored.valor_combinado, Decimal("137.45"))
            self.assertEqual(stored.produtor_id, self.ids["producer_a_id"])
            db.get(ProducaoModel, production_id).produtor_id = self.ids["producer_b_id"]
        self.assertEqual(
            self.http.get(f"/portal/produtor/producoes/{production_id}", headers=producer_a).status_code,
            404,
        )
        self.assertEqual(
            len(self.http.get("/portal/produtor/repasses", headers=producer_a).json()),
            1,
        )
        self.assertEqual(
            self.http.get("/portal/produtor/repasses", headers=producer_b).json(),
            [],
        )

        disabled = self.http.patch(
            f"/usuarios/{self.ids['producer_b_id']}",
            headers=admin,
            json={"ativo": False},
        )
        self.assertEqual(disabled.status_code, 200, disabled.text)
        self.assertEqual(
            self.http.get("/portal/produtor/producoes", headers=producer_b).status_code,
            401,
        )
        self.http.patch(
            f"/usuarios/{self.ids['producer_b_id']}",
            headers=admin,
            json={"ativo": True},
        )
        expired = jwt.encode(
            {
                "sub": "e2e-client-a",
                "type": "access",
                "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        self.assertEqual(
            self.http.get(
                "/portal/cliente/producoes",
                headers={"Authorization": "Bearer " + expired},
            ).status_code,
            401,
        )

        before = len(self.storage.objects)
        with self.SessionLocal() as db:
            rows_before_failure = db.query(ProducaoArquivoModel).count()
        with patch.object(
            producao_arquivo_service,
            "new_production_file_storage",
            return_value=FailingStorage(),
        ):
            failed = self.http.post(
                f"/producoes/{production_id}/arquivos",
                headers=admin,
                data={"tipo": "material"},
                files={"arquivo": ("fail.pdf", b"%PDF-fail", "application/pdf")},
            )
        self.assertEqual(failed.status_code, 503)
        self.assertEqual(len(self.storage.objects), before)
        with self.SessionLocal() as db:
            self.assertEqual(db.query(ProducaoArquivoModel).count(), rows_before_failure)

        compensating_storage = MemoryStorage()
        with self.SessionLocal() as db:
            production = db.get(ProducaoModel, production_id)
            actor = db.get(UsuarioModel, self.ids["admin_id"])
            with self.assertRaises(RuntimeError), patch.object(
                producao_arquivo_service.audit_service,
                "record",
                side_effect=RuntimeError("synthetic database failure"),
            ):
                producao_arquivo_service.upload(
                    db,
                    production=production,
                    actor=actor,
                    file_type="material",
                    filename="compensate.pdf",
                    mime_type="application/pdf",
                    data=b"%PDF-compensate",
                    visible_to_producer=True,
                    visible_to_client=False,
                    storage=compensating_storage,
                )
            self.assertFalse(compensating_storage.objects)
            self.assertEqual(len(compensating_storage.deleted), 1)
            self.assertEqual(
                db.query(ProducaoArquivoModel)
                .filter(ProducaoArquivoModel.nome_exibicao == "compensate.pdf")
                .count(),
                0,
            )

        inspector = inspect(self.engine)
        amount = next(
            column for column in inspector.get_columns("repasses_produtor")
            if column["name"] == "valor_combinado"
        )
        self.assertEqual((amount["type"].precision, amount["type"].scale), (12, 2))
        self.assertIn(
            "uq_repasses_produtor_producao_id",
            {item["name"] for item in inspector.get_unique_constraints("repasses_produtor")},
        )
        self.assertIn(
            "ck_repasses_produtor_status_valido",
            {item["name"] for item in inspector.get_check_constraints("repasses_produtor")},
        )
        with self.SessionLocal() as db:
            duplicate = RepasseProdutorModel(
                producao_id=production_id,
                produtor_id=self.ids["producer_b_id"],
                valor_combinado=Decimal("10.00"),
                moeda="BRL",
                status="definido",
            )
            db.add(duplicate)
            with self.assertRaises(IntegrityError):
                db.flush()
            db.rollback()
            self.assertGreater(
                db.query(AuditLogModel).filter(
                    AuditLogModel.action.in_(
                        ["production.progress_changed", "production.file_uploaded"]
                    )
                ).count(),
                0,
            )
            self.assertTrue(
                all(
                    row.object_key.startswith("arquivos/")
                    and "Cliente" not in row.object_key
                    for row in db.query(ProducaoArquivoModel).all()
                )
            )

    def test_browser_uses_real_backend_and_postgresql(self):
        from core.config import settings
        from models import (
            CobrancaModel,
            ProducaoArquivoModel,
            ProducaoModel,
            PropostaModel,
            RepasseProdutorModel,
        )

        root = Path(__file__).resolve().parents[2]
        env = {
            **os.environ,
            "E2E_PASSWORD": self.ids["password"],
            "E2E_FLOW_BUDGET_ID": str(self.ids["flow_budget_id"]),
            "E2E_PRODUCER_A_ID": str(self.ids["producer_a_id"]),
            "E2E_PROVISION_CLIENT_ID": str(self.ids["provision_client_id"]),
            "E2E_OTHER_PRODUCTION_ID": str(self.ids["other_production_id"]),
            "E2E_CLIENT_PROPOSAL_ID": str(self.ids["client_proposal_id"]),
            "E2E_OTHER_CLIENT_PROPOSAL_ID": str(self.ids["other_client_proposal_id"]),
        }
        previous = settings.COMMERCIAL_PIPELINE_V2_ENABLED
        settings.COMMERCIAL_PIPELINE_V2_ENABLED = True
        try:
            result = subprocess.run(
                [
                    os.getenv("NODE_BINARY", "node"),
                    str(root / "frontend/tests/portals_postgres_e2e.cjs"),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
        finally:
            settings.COMMERCIAL_PIPELINE_V2_ENABLED = previous
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PORTALS_E2E_PASS", result.stdout)
        with self.SessionLocal() as db:
            payout = db.query(RepasseProdutorModel).one()
            self.assertEqual(payout.status, "pago")
            self.assertEqual(payout.valor_combinado, Decimal("275.90"))
            files = db.query(ProducaoArquivoModel).all()
            self.assertGreaterEqual(len(files), 3)
            self.assertTrue(all(item.object_key not in result.stdout for item in files))
            proposal = db.get(PropostaModel, self.ids["client_proposal_id"])
            self.assertEqual(proposal.status, "aceita")
            self.assertEqual(
                db.query(CobrancaModel)
                .filter(CobrancaModel.proposta_id == proposal.id)
                .count(),
                1,
            )
            self.assertEqual(
                db.query(ProducaoModel)
                .filter(ProducaoModel.orcamento_id == proposal.orcamento_id)
                .count(),
                0,
            )


if __name__ == "__main__":
    unittest.main()
