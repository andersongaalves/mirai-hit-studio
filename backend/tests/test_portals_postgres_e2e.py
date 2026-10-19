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
from threading import Barrier, Event
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import httpx
from alembic.config import Config
from alembic.script import ScriptDirectory
from commercial_i2_support import local_frontend_server, local_server
from integrations.mercado_pago import MercadoPagoClient
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

        from commercial_i2_support import PaymentTransport
        from core.config import settings
        from database import SessionLocal, engine
        from main import app
        from routers.checkout import get_mercado_pago_client as public_provider
        from routers.portal_cliente import get_mercado_pago_client as portal_provider
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
        cls.payment_transport = PaymentTransport()
        cls.payment_transport.next_status = "processed"
        cls.payment_client = MercadoPagoClient(
            access_token="synthetic-postgres-e2e-token",
            session=cls.payment_transport,
        )
        app.dependency_overrides[public_provider] = lambda: cls.payment_client
        app.dependency_overrides[portal_provider] = lambda: cls.payment_client
        settings.PUBLIC_FRONTEND_URL = "http://localhost:4173"
        settings.AUDIO_TAG_WORKER_ENABLED = False

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
            AudioTagModel,
            AudioTagPerfilModel,
            AuditLogModel,
            AuthRateLimitModel,
            ClienteAcessoModel,
            ClienteModel,
            CobrancaModel,
            ConfigModel,
            OrcamentoModel,
            PagamentoModel,
            PortalNotificacaoModel,
            PortfolioEnvioModel,
            PreviaTagJobModel,
            ProducaoArquivoModel,
            ProducaoCotaArquivoModel,
            ProducaoEtapaAtribuicaoModel,
            ProducaoEtapaModel,
            ProducaoModel,
            ProducaoPoliticaModel,
            ProjetoModel,
            PropostaModel,
            ProviderWebhookEventModel,
            RepasseProdutorModel,
            ServicoModel,
            UsuarioModel,
        )

        with cls.SessionLocal.begin() as db:
            # Only this loopback PostgreSQL-17 fixture may reset append-only synthetic records.
            db.execute(text("TRUNCATE TABLE repasse_etapa_pagamentos, repasse_etapas, credito_etapas, credito_movimentos, credito_alocacoes, credito_lancamentos, credito_lotes, credito_contrato_itens RESTART IDENTITY"))
            for model in (
                AuditLogModel,
                AuthRateLimitModel,
                PreviaTagJobModel,
                AudioTagPerfilModel,
                AudioTagModel,
                ClienteAcessoModel,
                PortalNotificacaoModel,
                PortfolioEnvioModel,
                ProjetoModel,
                RepasseProdutorModel,
                ProducaoArquivoModel,
                ProviderWebhookEventModel,
                PagamentoModel,
                CobrancaModel,
                ProducaoEtapaAtribuicaoModel,
                ProducaoEtapaModel,
                ProducaoCotaArquivoModel,
                ProducaoPoliticaModel,
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
            admin_policy_budget = OrcamentoModel(
                nome_cliente=client_a.nome,
                email=client_a.email,
                servico="Política comercial E2E",
                cliente_id=client_a.id,
                valor_total=350.0,
                status="em_analise",
            )
            db.add_all([
                flow_budget,
                other_budget,
                completed_budget,
                invite_budget,
                client_proposal_budget,
                other_proposal_budget,
                admin_policy_budget,
            ])
            db.flush()
            proposal = PropostaModel(
                orcamento_id=flow_budget.id,
                numero="E2E-PROP-001",
                status="aceita",
                cliente_snapshot={
                    "cliente": {
                        "nome": client_a.nome,
                        "email": client_a.email,
                        "whatsapp": None,
                    },
                    "orcamento": {
                        "id": flow_budget.id,
                        "servico": flow_budget.servico,
                        "detalhes": None,
                        "valor_total": "1000.00",
                        "link_guia": None,
                    },
                },
                objeto="Mixagem E2E aceita",
                descricao="Proposta sintética aceita.",
                itens_json=[{
                    "descricao": "Mixagem",
                    "quantidade": "1",
                    "valor_unitario": "1000.00",
                    "desconto": "0.00",
                }],
                pagamentos_json=[],
                politica_pagamento="entrada_50_50",
                condicoes="Entrada de 50% para início.",
                totais_json={
                    "subtotal": "1000.00",
                    "desconto": "0.00",
                    "total": "1000.00",
                },
                enviada_em=datetime.now(timezone.utc),
                aprovada_em=datetime.now(timezone.utc),
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
            admin_policy_proposal = PropostaModel(
                orcamento_id=admin_policy_budget.id,
                numero="E2E-PROP-POLICY",
                status="rascunho",
                cliente_snapshot={
                    "cliente": {
                        "nome": client_a.nome,
                        "email": client_a.email,
                        "whatsapp": None,
                    },
                    "orcamento": {
                        "id": admin_policy_budget.id,
                        "servico": admin_policy_budget.servico,
                        "detalhes": None,
                        "valor_total": "350.00",
                        "link_guia": None,
                    },
                },
                objeto="Política comercial E2E",
                descricao="Rascunho sintético para persistência da política.",
                itens_json=[{
                    "descricao": "Produção musical",
                    "quantidade": "1",
                    "valor_unitario": "350.00",
                    "desconto": "0.00",
                }],
                pagamentos_json=[],
                politica_pagamento="entrada_50_50",
                condicoes="Condição definida pela política selecionada.",
                totais_json={
                    "subtotal": "350.00",
                    "desconto": "0.00",
                    "total": "350.00",
                },
            )
            db.add(admin_policy_proposal)
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
                "admin_policy_budget_id": admin_policy_budget.id,
                "admin_policy_proposal_id": admin_policy_proposal.id,
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

    def _create_commercial_lock_case(self, suffix, *, active_account=False):
        from core.security import get_password_hash
        from models import ClienteModel, OrcamentoModel, PropostaModel, UsuarioModel

        with self.SessionLocal.begin() as db:
            client = ClienteModel(
                nome=f"Lock Cliente {suffix}",
                email=f"lock-{suffix}@example.com",
            )
            db.add(client)
            db.flush()
            budget = OrcamentoModel(
                nome_cliente=client.nome,
                email=client.email,
                servico="Mixagem",
                valor_total=200.0,
                cliente_id=client.id,
                status="proposta_enviada",
            )
            db.add(budget)
            db.flush()
            proposal = PropostaModel(
                orcamento_id=budget.id,
                numero=f"LOCK-{suffix}",
                status="enviada",
                cliente_snapshot={
                    "cliente": {
                        "nome": client.nome,
                        "email": client.email,
                        "whatsapp": None,
                    },
                    "orcamento": {
                        "id": budget.id,
                        "servico": budget.servico,
                        "detalhes": None,
                        "valor_total": "200.00",
                        "link_guia": None,
                    },
                },
                objeto=f"Proposta concorrente {suffix}",
                descricao="Fixture sintética para validar a ordem dos locks.",
                itens_json=[{
                    "descricao": "Mixagem",
                    "quantidade": "1",
                    "valor_unitario": "200.00",
                    "desconto": "0.00",
                }],
                pagamentos_json=[],
                politica_pagamento="entrada_50_50",
                condicoes="Entrada de 50% para início.",
                totais_json={
                    "subtotal": "200.00",
                    "desconto": "0.00",
                    "total": "200.00",
                },
                enviada_em=datetime.now(timezone.utc),
            )
            db.add(proposal)
            db.flush()
            user_id = None
            if active_account:
                user = UsuarioModel(
                    username=f"lock-client-{suffix}",
                    password_hash=get_password_hash(self.ids["password"]),
                    role="cliente",
                    is_admin=False,
                    ativo=True,
                    cliente_id=client.id,
                )
                db.add(user)
                db.flush()
                user_id = user.id
            return {
                "proposal_id": proposal.id,
                "proposal_version": proposal.versao,
                "budget_id": budget.id,
                "client_id": client.id,
                "user_id": user_id,
            }

    def test_commercial_lock_order_postgresql17_concurrency_matrix(self):
        from core.config import settings
        from models import (
            ClienteAcessoModel,
            CobrancaModel,
            PropostaModel,
            UsuarioModel,
        )
        from services import client_access_service as access
        from services import portal_cliente_proposta_service as portal_proposals
        from services import proposta_comercial_service as commercial
        from services import proposta_service
        from services.email_service import EmailService

        expected_conflicts = (
            access.ClientAccessError,
            proposta_service.PropostaNaoEncontrada,
            proposta_service.PropostaInvalida,
            proposta_service.PropostaConflito,
        )

        def race(*operations):
            gate = Barrier(len(operations))

            def run(operation):
                with self.SessionLocal() as db:
                    gate.wait(timeout=10)
                    try:
                        operation(db)
                        return "ok"
                    except expected_conflicts as error:
                        return type(error).__name__

            with ThreadPoolExecutor(max_workers=len(operations)) as pool:
                futures = [pool.submit(run, operation) for operation in operations]
                return [future.result(timeout=20) for future in futures]

        def invite(case, source):
            def operation(db):
                access.invite(
                    db,
                    case["proposal_id"],
                    db.get(UsuarioModel, self.ids["admin_id"]),
                    f"request-{source}",
                    source,
                )

            return operation

        def admin_accept(case, request_id):
            def operation(db):
                commercial.aprovar(
                    db,
                    case["proposal_id"],
                    db.get(UsuarioModel, self.ids["admin_id"]),
                    request_id,
                )

            return operation

        def client_accept(case, request_id):
            def operation(db):
                portal_proposals.accept(
                    db,
                    case["proposal_id"],
                    case["client_id"],
                    case["proposal_version"],
                    db.get(UsuarioModel, case["user_id"]),
                    request_id,
                )

            return operation

        def client_refuse(case, request_id):
            def operation(db):
                portal_proposals.refuse(
                    db,
                    case["proposal_id"],
                    case["client_id"],
                    case["proposal_version"],
                    db.get(UsuarioModel, case["user_id"]),
                    request_id,
                )

            return operation

        def resend(case, source):
            def operation(db):
                access.resend(
                    db,
                    case["proposal_id"],
                    db.get(UsuarioModel, self.ids["admin_id"]),
                    f"request-{source}",
                    source,
                )

            return operation

        def assert_case(case, *, users, accesses, charges_at_most):
            with self.SessionLocal() as db:
                proposal = db.get(PropostaModel, case["proposal_id"])
                self.assertIn(proposal.status, {"enviada", "aceita", "recusada"})
                self.assertEqual(
                    db.query(UsuarioModel).filter_by(cliente_id=case["client_id"]).count(),
                    users,
                )
                self.assertEqual(
                    db.query(ClienteAcessoModel).filter_by(cliente_id=case["client_id"]).count(),
                    accesses,
                )
                self.assertLessEqual(
                    db.query(CobrancaModel).filter_by(proposta_id=case["proposal_id"]).count(),
                    charges_at_most,
                )

        previous = settings.COMMERCIAL_PIPELINE_V2_ENABLED
        settings.COMMERCIAL_PIPELINE_V2_ENABLED = True
        try:
            with (
                patch.object(
                    EmailService,
                    "enviar_convite_cliente",
                    return_value={"id": "lock-invite"},
                ),
                patch.object(
                    EmailService,
                    "enviar_proposta_disponivel",
                    return_value={"id": "lock-notice"},
                ),
            ):
                invite_admin = self._create_commercial_lock_case("INVITE-ADMIN")
                self.assertEqual(
                    race(
                        invite(invite_admin, "invite-admin"),
                        admin_accept(invite_admin, "accept-admin"),
                    ),
                    ["ok", "ok"],
                )
                assert_case(invite_admin, users=0, accesses=1, charges_at_most=1)

                invite_client = self._create_commercial_lock_case(
                    "INVITE-CLIENT", active_account=True
                )
                self.assertEqual(
                    race(
                        invite(invite_client, "invite-client"),
                        client_accept(invite_client, "accept-client"),
                    ),
                    ["ok", "ok"],
                )
                assert_case(invite_client, users=1, accesses=0, charges_at_most=1)

                double_invite = self._create_commercial_lock_case("DOUBLE-INVITE")
                double_results = race(
                    invite(double_invite, "double-a"),
                    invite(double_invite, "double-b"),
                )
                self.assertEqual(double_results.count("ok"), 1)
                self.assertEqual(double_results.count("ClientAccessConflict"), 1)
                assert_case(double_invite, users=0, accesses=1, charges_at_most=0)

                invite_refuse = self._create_commercial_lock_case(
                    "INVITE-REFUSE", active_account=True
                )
                refuse_results = race(
                    invite(invite_refuse, "invite-refuse"),
                    client_refuse(invite_refuse, "refuse-client"),
                )
                self.assertIn(refuse_results[0], {"ok", "ClientAccessInvalid"})
                self.assertEqual(refuse_results[1], "ok")
                assert_case(invite_refuse, users=1, accesses=0, charges_at_most=0)

                resend_accept = self._create_commercial_lock_case("RESEND-ACCEPT")
                with self.SessionLocal() as db:
                    invite(resend_accept, "resend-seed")(db)
                resend_results = race(
                    resend(resend_accept, "resend-race"),
                    admin_accept(resend_accept, "resend-accept"),
                )
                self.assertEqual(resend_results, ["ok", "ok"])
                assert_case(resend_accept, users=0, accesses=1, charges_at_most=1)
        finally:
            settings.COMMERCIAL_PIPELINE_V2_ENABLED = previous

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

    def test_metadata_bootstrap_private_tables_postgresql17(self):
        with self.SessionLocal() as db:
            rows = db.execute(text("""
                SELECT relname, relrowsecurity FROM pg_class
                WHERE relnamespace = 'public'::regnamespace
                  AND relname IN ('audio_tag_perfis', 'audio_tags', 'portal_notificacoes',
                                  'portfolio_envios', 'previa_tag_jobs', 'projeto_creditos',
                                  'credito_lotes', 'credito_lancamentos', 'credito_contrato_itens',
                                  'credito_alocacoes', 'credito_movimentos', 'credito_etapas',
                                  'repasse_etapas', 'repasse_etapa_pagamentos')
                ORDER BY relname
            """)).all()
            self.assertEqual(rows, [('audio_tag_perfis', True), ('audio_tags', True),
                                    ('credito_alocacoes', True), ('credito_contrato_itens', True),
                                    ('credito_etapas', True), ('credito_lancamentos', True), ('credito_lotes', True), ('credito_movimentos', True), ('portal_notificacoes', True),
                                    ('portfolio_envios', True), ('previa_tag_jobs', True), ('projeto_creditos', True),
                                    ('repasse_etapa_pagamentos', True), ('repasse_etapas', True)])
            for role in ('anon', 'authenticated'):
                exists = db.execute(text('SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=:role)'),
                                    {'role': role}).scalar_one()
                if exists:
                    for table, _ in rows:
                        self.assertFalse(db.execute(text("SELECT has_table_privilege(:role, :table, 'SELECT')"),
                                                    {'role': role, 'table': 'public.' + table}).scalar_one())
                    self.assertFalse(db.execute(text("""
                        SELECT has_sequence_privilege(:role, 'public.projeto_creditos_id_seq', 'USAGE')
                    """), {'role': role}).scalar_one())

    @patch("core.config.settings.COMMERCIAL_PIPELINE_V2_ENABLED", True)
    def test_service_credits_postgresql17_concurrency_immutability_and_ownership(self):
        from models import (
            CobrancaModel,
            CreditoContratoItemModel,
            CreditoLancamentoModel,
            CreditoLoteModel,
            OrcamentoModel,
            ProducaoModel,
            PropostaModel,
            ServicoEtapaModel,
            ServicoModel,
        )
        from schemas.proposta import PropostaUpdate
        from services import (
            financial_service,
            producao_liberacao_service,
            proposta_service,
            proposta_snapshot_service,
        )
        from sqlalchemy.exc import DBAPIError

        with self.SessionLocal() as db:
            catalog = db.scalar(select(ServicoModel).order_by(ServicoModel.id))
            catalog.credito_servico = {"unidade": "canal", "quantidade": "10"}
            db.add(ServicoEtapaModel(servico_id=catalog.id, ordem=1, nome="Execucao", peso_percentual=100))
            budget = OrcamentoModel(nome_cliente="Sintetico creditos", email="synthetic@example.invalid",
                                    servico="Mix", cliente_id=self.ids["client_a_id"])
            db.add(budget)
            db.commit()
            budget_id = budget.id
            proposal = proposta_service.criar_por_orcamento(db, budget_id)
            proposta_service.atualizar(db, proposal.id, PropostaUpdate(finalidade="creditos", politica_pagamento="integral",
                itens=[{"descricao": "Creditos sinteticos", "quantidade": 2, "valor_unitario": "500", "servico_id": catalog.id}]))
            model = db.get(PropostaModel, proposal.id)
            proposta_snapshot_service.congelar(db, model, origem="envio", estrito=True)
            model.status, model.enviada_em = "aceita", datetime.now(timezone.utc)
            budget.status = "aprovado"
            charge = financial_service.criar_para_proposta(db, model, cliente_id=self.ids["client_a_id"])
            financial_service.registrar_pagamento(db, charge.id, tipo="integral", valor="1000", status="aprovado")
            charge_id = charge.id
            db.commit()

        barrier = Barrier(2)

        def grant():
            with self.SessionLocal() as db:
                db.execute(text("SET LOCAL lock_timeout='5s'"))
                db.execute(text("SET LOCAL statement_timeout='10s'"))
                barrier.wait(timeout=10)
                producao_liberacao_service.avaliar_liberacao_producao(db, charge_id)
                db.commit()

        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = pool.submit(grant), pool.submit(grant)
            first.result(timeout=20)
            second.result(timeout=20)
        with self.SessionLocal() as db:
            lots = db.scalars(select(CreditoLoteModel).where(CreditoLoteModel.cobranca_id == charge_id)).all()
            self.assertEqual(len(lots), 1)
            lot_id = lots[0].id
            self.assertEqual(lots[0].quantidade, Decimal(20))
            self.assertEqual(len(db.scalars(select(CreditoLancamentoModel)).all()), 1)
            self.assertIsNone(db.scalar(select(ProducaoModel).where(ProducaoModel.orcamento_id == budget_id)))
            self.assertEqual(len(db.get(CobrancaModel, charge_id).pagamentos), 1)
            source_id = db.scalar(select(CreditoContratoItemModel.id))
            service_id = lots[0].servico_id
        admin = self._login("e2e-admin")
        self.assertEqual(self.http.delete(f"/servicos/{service_id}", headers=admin).status_code, 409)
        for statement in (
            "UPDATE credito_contrato_itens SET quantidade=21 WHERE id=:id",
            "DELETE FROM credito_contrato_itens WHERE id=:id",
        ):
            with self.assertRaises(DBAPIError) as error, self.engine.begin() as connection:
                connection.execute(text(statement), {"id": source_id})
            self.assertEqual(error.exception.orig.pgcode, "P0001")
        for statement in (
            "UPDATE credito_lotes SET quantidade=21 WHERE id=:id",
            "DELETE FROM credito_lotes WHERE id=:id",
            "UPDATE credito_lancamentos SET quantidade=21 WHERE lote_id=:id",
            "DELETE FROM credito_lancamentos WHERE lote_id=:id",
        ):
            with self.assertRaises(DBAPIError) as error, self.engine.begin() as connection:
                connection.execute(text(statement), {"id": lot_id})
            self.assertEqual(error.exception.orig.pgcode, "P0001")
        client = self._login("e2e-client-a")
        response = self.http.get("/portal/cliente/creditos", headers=client)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["saldos"][0]["disponivel"], "20.000")
        self.assertEqual(self.http.get(f"/clientes/{self.ids['client_a_id']}/creditos", headers=admin).json(), response.json())
        other = self._login("e2e-client-b")
        self.assertEqual(self.http.get("/portal/cliente/creditos", headers=other).json()["lotes"], [])
        producer = self._login("e2e-producer-a")
        self.assertEqual(self.http.get("/portal/cliente/creditos", headers=producer).status_code, 403)
        self.assertEqual(self.http.get(f"/clientes/{self.ids['client_a_id']}/creditos", headers=other).status_code, 403)
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [os.getenv("NODE_BINARY", "node"), str(root / "frontend/tests/service_credits.cjs")],
            cwd=root, env={**os.environ, "MIRAI_CREDITS_REAL_BACKEND": REQUIRED_ACK, "E2E_PASSWORD": self.ids["password"]},
            capture_output=True, text=True, timeout=120, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("CREDITS_POSTGRES_BROWSER_PASS", result.stdout)

    @patch("core.config.settings.COMMERCIAL_PIPELINE_V2_ENABLED", True)
    def test_stage_payout_postgresql17_concurrency_receipts_immutability_and_ownership(self):
        from uuid import uuid4

        from models import (
            OrcamentoModel,
            PagamentoModel,
            ProducaoModel,
            RepasseEtapaModel,
            RepasseEtapaPagamentoModel,
            ServicoEtapaModel,
            ServicoModel,
            UsuarioModel,
        )
        from schemas.proposta import PropostaUpdate
        from services import (
            financial_service,
            producao_etapa_service,
            producao_liberacao_service,
            proposta_service,
            proposta_snapshot_service,
        )
        from sqlalchemy import func
        from sqlalchemy.exc import DBAPIError

        with self.SessionLocal() as db:
            actor = db.get(UsuarioModel, self.ids["admin_id"])
            catalog = db.scalar(select(ServicoModel).order_by(ServicoModel.id))
            db.add(ServicoEtapaModel(servico_id=catalog.id, ordem=1, nome="Mixagem", peso_percentual=100))
            budget = OrcamentoModel(nome_cliente="Sintetico repasse", email="synthetic@example.invalid", servico="Mix",
                                    cliente_id=self.ids["client_a_id"])
            db.add(budget)
            db.commit()
            proposal = proposta_service.criar_por_orcamento(db, budget.id)
            proposta_service.atualizar(db, proposal.id, PropostaUpdate(politica_pagamento="integral",
                produtor_id=self.ids["producer_a_id"], itens=[{"descricao": "Mix", "quantidade": 1,
                    "valor_unitario": "50000000.00", "servico_id": catalog.id}]))
            proposta_snapshot_service.congelar(db, proposal, origem="envio", estrito=True)
            proposal.status = "aceita"
            db.flush()
            charge = financial_service.criar_para_proposta(db, proposal, cliente_id=self.ids["client_a_id"])
            financial_service.registrar_pagamento(db, charge.id, tipo="integral", valor="50000000.00", status="aprovado")
            producao_liberacao_service.avaliar_liberacao_producao(db, charge.id)
            db.commit()
            production = db.scalar(select(ProducaoModel).where(ProducaoModel.orcamento_id == budget.id))
            production_id, charge_id = production.id, charge.id
            stage = producao_etapa_service._etapas(db, production_id)[0]
            for status in ("em_andamento", "concluida"):
                producao_etapa_service.atualizar(db, production, stage.id, papel="admin", usuario=actor, status=status)
            production.status = "finalizado"
            db.commit()
        admin = self._login("e2e-admin")
        producer = self._login("e2e-producer-a")
        other = self._login("e2e-producer-b")
        client = self._login("e2e-client-a")
        endpoint = f"/producoes/{production_id}/repasses-etapas"
        for denied in (producer, client):
            self.assertEqual(self.http.post(endpoint, headers=denied).status_code, 403)
        barrier = Barrier(2)

        def issue():
            barrier.wait(timeout=10)
            return self.http.post(endpoint, headers=admin, timeout=20)

        with ThreadPoolExecutor(max_workers=2) as pool:
            tasks = [pool.submit(issue) for _ in range(2)]
            issued = [task.result(timeout=25) for task in tasks]
        self.assertEqual([response.status_code for response in issued], [200, 200])
        record = issued[0].json()[0]
        self.assertEqual((record["bruto_centavos"], record["produtor_centavos"], record["mirai_centavos"]), (5000000000, 4000000000, 1000000000))
        self.assertEqual(self.http.get("/portal/produtor/repasses-etapas", headers=other).json(), [])
        own = self.http.get("/portal/produtor/repasses-etapas", headers=producer)
        self.assertEqual(own.status_code, 200)
        self.assertEqual(own.json()[0]["id"], record["id"])
        self.assertEqual(own.headers["cache-control"], "private, no-store")
        self.assertEqual(self.http.get(f'/portal/produtor/repasses-etapas/{record["id"]}/comprovante', headers=other).status_code, 404)
        barrier = Barrier(2)
        payment = {"referencia": "TRANSFERENCIA-SINTETICA", "idempotency_key": str(uuid4())}

        def register_payment():
            barrier.wait(timeout=10)
            return self.http.post(f'{endpoint}/{record["id"]}/pagamento', headers=admin, json=payment, timeout=20)

        with ThreadPoolExecutor(max_workers=2) as pool:
            tasks = [pool.submit(register_payment) for _ in range(2)]
            paid = [task.result(timeout=25) for task in tasks]
        self.assertEqual([response.status_code for response in paid], [200, 200])
        self.assertEqual(paid[0].json()[0]["estado"], "pago")
        with self.SessionLocal() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(RepasseEtapaModel)), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(RepasseEtapaPagamentoModel)), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(PagamentoModel).where(PagamentoModel.cobranca_id == charge_id)), 1)
        for statement in ("UPDATE repasse_etapas SET produtor_centavos=1", "DELETE FROM repasse_etapas",
                          "UPDATE repasse_etapa_pagamentos SET referencia='alterada'", "DELETE FROM repasse_etapa_pagamentos"):
            with self.assertRaises(DBAPIError) as error, self.engine.begin() as connection:
                connection.execute(text(statement))
            self.assertEqual(error.exception.orig.pgcode, "P0001")

    @patch("core.config.settings.COMMERCIAL_PIPELINE_V2_ENABLED", True)
    def test_credit_allocation_postgresql17_conservation_and_duplicate_consumption(self):
        from uuid import uuid4

        from models import (
            CreditoAlocacaoModel,
            CreditoEtapaModel,
            CreditoLoteModel,
            CreditoMovimentoModel,
            OrcamentoModel,
            ProducaoEtapaModel,
            ProducaoModel,
            PropostaModel,
            ServicoEtapaModel,
            ServicoModel,
            UsuarioModel,
        )
        from schemas.credito_alocacao import MovimentoCreditos, ReservaCreditos
        from schemas.proposta import PropostaUpdate
        from services import (
            carteira_creditos_service,
            credito_alocacao_service,
            financial_service,
            producao_etapa_service,
            producao_liberacao_service,
            proposta_service,
            proposta_snapshot_service,
        )
        from sqlalchemy.exc import DBAPIError

        with self.SessionLocal() as db:
            actor = db.scalar(select(UsuarioModel).where(UsuarioModel.username == "e2e-admin"))
            actor_id = actor.id
            catalog = db.scalar(select(ServicoModel).order_by(ServicoModel.id))
            catalog.credito_servico = {"unidade": "canal", "quantidade": "20"}
            db.add(ServicoEtapaModel(servico_id=catalog.id, ordem=1, nome="Execucao", peso_percentual=100))
            source = OrcamentoModel(nome_cliente="Sintetico", email="synthetic@example.invalid", servico="Mix",
                                    cliente_id=self.ids["client_a_id"])
            target = OrcamentoModel(nome_cliente="Sintetico", email="synthetic@example.invalid", servico="Mix",
                                    cliente_id=self.ids["client_a_id"])
            other_target = OrcamentoModel(nome_cliente="Sintetico", email="synthetic@example.invalid", servico="Mix",
                                          cliente_id=self.ids["client_a_id"])
            db.add_all([source, target, other_target])
            db.commit()
            proposal = proposta_service.criar_por_orcamento(db, source.id)
            proposta_service.atualizar(db, proposal.id, PropostaUpdate(finalidade="creditos", politica_pagamento="integral",
                itens=[{"descricao": "Credito sintetico", "quantidade": 1, "valor_unitario": "1000", "servico_id": catalog.id}]))
            model = db.get(PropostaModel, proposal.id)
            proposta_snapshot_service.congelar(db, model, origem="envio", estrito=True)
            model.status, model.enviada_em = "aceita", datetime.now(timezone.utc)
            charge = financial_service.criar_para_proposta(db, model, cliente_id=self.ids["client_a_id"])
            financial_service.registrar_pagamento(db, charge.id, tipo="integral", valor="1000", status="aprovado")
            producao_liberacao_service.avaliar_liberacao_producao(db, charge.id)
            production = ProducaoModel(titulo="Uso sintetico", cliente="Sintetico", servico="Mix", orcamento_id=target.id,
                                       status="aguardando_inicio")
            db.add(production)
            other_production = ProducaoModel(titulo="Outro uso sintetico", cliente="Sintetico", servico="Mix",
                                             orcamento_id=other_target.id, status="aguardando_inicio")
            db.add(other_production)
            db.commit()
            production_id = production.id
            other_production_id = other_production.id
            lot_id = db.scalar(select(CreditoLoteModel.id))

        barrier = Barrier(2)

        def reserve(target_id):
            with self.SessionLocal() as db:
                db.execute(text("SET LOCAL lock_timeout='5s'"))
                db.execute(text("SET LOCAL statement_timeout='10s'"))
                actor = db.get(UsuarioModel, actor_id)
                data = ReservaCreditos(lote_id=lot_id, quantidade="15", motivo="Reserva sintetica", idempotency_key=uuid4())
                barrier.wait(timeout=10)
                try:
                    result = credito_alocacao_service.reservar(db, target_id, data, actor=actor)
                    return result["id"], target_id
                except credito_alocacao_service.AlocacaoConflito:
                    return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = pool.submit(reserve, production_id), pool.submit(reserve, other_production_id)
            results = [first.result(timeout=20), second.result(timeout=20)]
        self.assertEqual(sum(item is not None for item in results), 1)
        allocation_id, production_id = next(item for item in results if item is not None)
        with self.SessionLocal() as db:
            balance = carteira_creditos_service.carteira(db, self.ids["client_a_id"])["saldos"][0]
            self.assertEqual(Decimal(balance["disponivel"]), Decimal(5))
            self.assertEqual(Decimal(balance["reservado"]), Decimal(15))
            db.get(ProducaoModel, production_id).status = "em_producao"
            db.commit()
        barrier = Barrier(2)
        key = uuid4()

        def consume():
            with self.SessionLocal() as db:
                db.execute(text("SET LOCAL lock_timeout='5s'"))
                actor = db.get(UsuarioModel, actor_id)
                data = MovimentoCreditos(tipo="consumo", motivo="Consumo sintetico", idempotency_key=key)
                barrier.wait(timeout=10)
                return credito_alocacao_service.movimentar(db, production_id, allocation_id, data, actor=actor)["estado"]

        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = pool.submit(consume), pool.submit(consume)
            self.assertEqual([first.result(timeout=20), second.result(timeout=20)], ["consumida", "consumida"])
        with self.SessionLocal() as db:
            self.assertEqual(len(db.scalars(select(CreditoAlocacaoModel)).all()), 1)
            self.assertEqual(len(db.scalars(select(CreditoMovimentoModel)).all()), 2)
            balance = carteira_creditos_service.carteira(db, self.ids["client_a_id"])["saldos"][0]
            self.assertEqual(Decimal(balance["consumido"]), Decimal(15))
            stage_id = db.scalar(select(CreditoEtapaModel.etapa_id).where(CreditoEtapaModel.alocacao_id == allocation_id))
            self.assertIsNotNone(stage_id)
            self.assertEqual(db.get(ProducaoEtapaModel, stage_id).valor, Decimal(750))
            db.get(ProducaoModel, production_id).status = "aguardando_inicio"
            db.commit()
        barrier = Barrier(2)

        def start_or_reverse(start):
            with self.SessionLocal() as db:
                db.execute(text("SET LOCAL lock_timeout='5s'"))
                db.execute(text("SET LOCAL statement_timeout='10s'"))
                actor = db.get(UsuarioModel, actor_id)
                production = db.get(ProducaoModel, production_id)
                barrier.wait(timeout=10)
                try:
                    if start:
                        producao_etapa_service.atualizar(db, production, stage_id, papel="admin", usuario=actor,
                            status="em_andamento", status_atual="pendente")
                    else:
                        credito_alocacao_service.movimentar(db, production_id, allocation_id,
                            MovimentoCreditos(tipo="estorno", motivo="Estorno sintetico", idempotency_key=uuid4()), actor=actor)
                    return True
                except (credito_alocacao_service.AlocacaoConflito, producao_etapa_service.EtapaConflito,
                        producao_etapa_service.EtapaNaoEncontrada):
                    return False

        with ThreadPoolExecutor(max_workers=2) as pool:
            start, reverse = pool.submit(start_or_reverse, True), pool.submit(start_or_reverse, False)
            started, reversed_ = start.result(timeout=20), reverse.result(timeout=20)
        self.assertEqual(int(started) + int(reversed_), 1)
        expected_state = "consumida" if started else "estornada"
        with self.SessionLocal() as db:
            balance = carteira_creditos_service.carteira(db, self.ids["client_a_id"])["saldos"][0]
            self.assertEqual(Decimal(balance["disponivel"]), Decimal(5) if started else Decimal(20))
            self.assertEqual(credito_alocacao_service.listar(db, production_id)[0]["estado"], expected_state)
        for table in ("credito_alocacoes", "credito_movimentos"):
            for statement in (f"UPDATE {table} SET motivo='adulterado'", f"DELETE FROM {table}"):
                with self.assertRaises(DBAPIError) as error, self.engine.begin() as connection:
                    connection.execute(text(statement))
                self.assertEqual(error.exception.orig.pgcode, "P0001")
        for statement in ("UPDATE credito_etapas SET ordem_no_item=99", "DELETE FROM credito_etapas"):
            with self.assertRaises(DBAPIError) as error, self.engine.begin() as connection:
                connection.execute(text(statement))
            self.assertEqual(error.exception.orig.pgcode, "P0001")
        producer = self._login("e2e-producer-a")
        self.assertEqual(self.http.get(f"/producoes/{production_id}/creditos", headers=producer).status_code, 403)
        admin = self._login("e2e-admin")
        response = self.http.get(f"/producoes/{production_id}/creditos", headers=admin)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()[0]["estado"], expected_state)
        creation = {"lote_id": lot_id, "quantidade": "3", "motivo": "Producao sintetica",
                    "titulo": "Faixa sintetica", "produtor_id": self.ids["producer_a_id"], "idempotency_key": str(uuid4())}
        endpoint = f"/producoes/creditos/cliente/{self.ids['client_a_id']}"
        self.assertEqual(self.http.post(endpoint, headers=producer, json=creation).status_code, 403)
        first = self.http.post(endpoint, headers=admin, json=creation)
        second = self.http.post(endpoint, headers=admin, json=creation)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(first.json()["producao_id"], second.json()["producao_id"])

    def test_audio_tags_postgresql17_worker_claim_and_private_original(self):
        import io
        import wave

        from models import PreviaTagJobModel, ProducaoArquivoModel
        from services import audio_tag_service

        admin = self._login("e2e-admin")
        producer = self._login("e2e-producer-a")
        client = self._login("e2e-client-a")
        other = self._login("e2e-client-b")
        production_id = self._create_flow_production(admin)
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(22050)
            audio.writeframes(b'\x00\x00' * 2205)
        original = buffer.getvalue()
        uploaded_tag = self.http.post('/admin/audio-tag', headers=admin, data={'versao': '0'},
                                      files={'arquivo': ('synthetic.wav', original, 'audio/wav')})
        self.assertEqual(uploaded_tag.status_code, 200, uploaded_tag.text)
        uploaded = self.http.post(f'/portal/produtor/producoes/{production_id}/arquivos', headers=producer,
                                  data={'tipo': 'previa'}, files={'arquivo': ('preview.wav', original, 'audio/wav')})
        self.assertEqual(uploaded.status_code, 201, uploaded.text)
        file_id = uploaded.json()['id']
        self.assertEqual(uploaded.json()['processamento_tag'], 'pendente')
        entered, release = Event(), Event()

        def renderer(*args):
            entered.set()
            if not release.wait(timeout=10):
                raise RuntimeError('synthetic worker timeout')
            return b'synthetic tagged mp3'

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(audio_tag_service.processar_um, self.SessionLocal, storage=self.storage, renderer=renderer)
            try:
                self.assertTrue(entered.wait(timeout=10))
                second = pool.submit(audio_tag_service.processar_um, self.SessionLocal, storage=self.storage, renderer=renderer)
                self.assertFalse(second.result(timeout=5))
                self.assertEqual(self.http.get(f'/portal/cliente/arquivos/{file_id}/conteudo', headers=client).status_code, 503)
                self.assertEqual(self.http.get(f'/portal/cliente/arquivos/{file_id}/conteudo', headers=other).status_code, 404)
            finally:
                release.set()
            self.assertTrue(first.result(timeout=10))
        with self.SessionLocal() as db:
            model = db.get(ProducaoArquivoModel, file_id)
            job = db.get(PreviaTagJobModel, file_id)
            self.assertFalse(model.visivel_cliente)
            self.assertTrue(model.original_restrito)
            self.assertEqual(job.estado, 'pronto')
            self.assertEqual(job.sha256, sha256(b'synthetic tagged mp3').hexdigest())
            self.assertEqual(len(self.storage.objects), 2)
        result = self.http.get(f'/portal/cliente/arquivos/{file_id}/conteudo', headers=client)
        self.assertEqual(result.content, b'synthetic tagged mp3')
        self.assertEqual(self.http.get(f'/portal/produtor/arquivos/{file_id}/conteudo', headers=producer).content, original)

    def test_portfolio_submission_postgresql17_concurrent_review(self):
        from models import PortfolioEnvioModel, ProjetoModel, UsuarioModel
        from schemas.portfolio_envio import PortfolioEnvioRevisao
        from services import portfolio_envio_service

        producer = self._login("e2e-producer-a")
        other = self._login("e2e-producer-b")
        admin = self._login("e2e-admin")
        production_id = self._create_flow_production(admin)
        payload = {
            "request_id": str(uuid.uuid4()), "producao_id": production_id,
            "titulo": "Portfolio sintetico", "artista": "Artista sintetico", "categoria": "Mixagem",
            "link_audio": "https://example.test/song.mp3", "link_capa": "https://example.test/cover.png",
            "vertical": "artists", "case_type": "demo", "autorizacao_artista": True,
        }
        self.assertEqual(self.http.post("/portal/produtor/portfolio", headers=other, json=payload).status_code, 404)
        gate = Barrier(2)

        def submit():
            gate.wait(timeout=10)
            return self.http.post("/portal/produtor/portfolio", headers=producer, json=payload)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [task.result(timeout=35) for task in [pool.submit(submit), pool.submit(submit)]]
        self.assertEqual([r.status_code for r in results], [201, 201])
        envio_id = results[0].json()["id"]
        self.assertEqual(envio_id, results[1].json()["id"])
        self.assertEqual(self.http.get("/portal/produtor/portfolio", headers=other).json(), [])
        with self.SessionLocal() as db:
            before = db.query(ProjetoModel).count()
        gate = Barrier(2)

        def approve():
            with self.SessionLocal() as db:
                db.execute(text("SET LOCAL lock_timeout='5s'"))
                db.execute(text("SET LOCAL statement_timeout='8s'"))
                actor = db.scalar(select(UsuarioModel).where(UsuarioModel.username == "e2e-admin"))
                gate.wait(timeout=10)
                return portfolio_envio_service.revisar(
                    db, actor, envio_id, PortfolioEnvioRevisao(versao=1, decisao="aprovar"),
                ).projeto_id

        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = [task.result(timeout=20) for task in [pool.submit(approve), pool.submit(approve)]]
        self.assertEqual(ids[0], ids[1])
        with self.SessionLocal() as db:
            self.assertEqual(db.query(PortfolioEnvioModel).count(), 1)
            self.assertEqual(db.query(ProjetoModel).count(), before + 1)
            project = db.get(ProjetoModel, ids[0])
            self.assertEqual(project.creditos[0].usuario_id, self.ids["producer_a_id"])
            # Remove only this test's public project before the standard fixture cleanup.
            db.delete(db.get(PortfolioEnvioModel, envio_id))
            db.delete(project)
            db.commit()

    def test_portal_notifications_postgresql17_concurrent_insert_and_seen_claim(self):
        from models import (
            CobrancaModel,
            PagamentoModel,
            PortalNotificacaoModel,
            ProducaoModel,
        )
        from services import portal_notificacao_service as notifications

        admin = self._login("e2e-admin")
        production_id = self._create_flow_production(admin)
        client = self._login("e2e-client-a")
        other_client = self._login("e2e-client-b")
        with self.SessionLocal() as db:
            before = (db.query(CobrancaModel).count(), db.query(PagamentoModel).count())
            self.assertTrue(db.execute(text(
                "SELECT relrowsecurity FROM pg_class WHERE oid='public.portal_notificacoes'::regclass"
            )).scalar_one())
        gate = Barrier(2)

        def emit():
            with self.SessionLocal.begin() as db:
                db.execute(text("SET LOCAL lock_timeout='5s'"))
                db.execute(text("SET LOCAL statement_timeout='8s'"))
                production = db.get(ProducaoModel, production_id)
                gate.wait(timeout=10)
                notifications.emitir_producao(db, production, "nova_mensagem", f"concurrent:{production_id}")

        with ThreadPoolExecutor(max_workers=2) as pool:
            tasks = [pool.submit(emit) for _ in range(2)]
            for task in tasks:
                task.result(timeout=20)
        result = self.http.get("/portal/notificacoes", headers=client)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["nao_vistas"], 1)
        event_id = result.json()["itens"][0]["id"]
        self.assertEqual(self.http.get("/portal/notificacoes", headers=other_client).json()["itens"], [])
        path = "/portal/notificacoes/vistas"
        self.assertEqual(self.http.post(path, headers=other_client, json={"ids": [event_id]}).json(), [])
        gate = Barrier(2)

        def claim():
            gate.wait(timeout=10)
            response = self.http.post(path, headers=client, json={"ids": [event_id]}, timeout=15)
            self.assertEqual(response.status_code, 200, response.text)
            return response.json()

        with ThreadPoolExecutor(max_workers=2) as pool:
            tasks = [pool.submit(claim) for _ in range(2)]
            claims = [task.result(timeout=20) for task in tasks]
        self.assertEqual(sorted(len(items) for items in claims), [0, 1])
        self.assertEqual(self.http.post(path, headers=client, json={"ids": [event_id]}).json(), [])
        self.assertEqual(self.http.get("/portal/notificacoes", headers=client).json()["nao_vistas"], 0)
        with self.SessionLocal() as db:
            self.assertEqual(db.query(PortalNotificacaoModel).count(), 1)
            self.assertEqual((db.query(CobrancaModel).count(), db.query(PagamentoModel).count()), before)

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

    def test_pix_cancel_and_webhook_approval_race_postgresql17(self):
        from commercial_i2_support import FakeResponse, signed_webhook
        from core.config import settings
        from models import CobrancaModel, PagamentoModel, ProducaoModel, PropostaModel
        from routers.webhooks import get_mercado_pago_client as webhook_provider

        previous_v2 = settings.COMMERCIAL_PIPELINE_V2_ENABLED
        previous_secret = settings.MERCADO_PAGO_WEBHOOK_SECRET
        previous_status = self.payment_transport.next_status
        previous_session = self.payment_client._session
        previous_webhook_override = self.app.dependency_overrides.get(webhook_provider)
        secret = "e2e-synthetic-webhook-secret"
        cancel_started, allow_cancel = Event(), Event()
        transport = self.payment_transport

        class PaymentWinsCancel:
            def request(self, method, url, **kwargs):
                if method == "POST" and url.endswith("/cancel"):
                    cancel_started.set()
                    if not allow_cancel.wait(timeout=10):
                        raise AssertionError("synthetic cancel race timed out")
                    return FakeResponse({"code": "cannot_cancel_order"}, status=409)
                return transport.request(method, url, **kwargs)

        settings.COMMERCIAL_PIPELINE_V2_ENABLED = True
        settings.MERCADO_PAGO_WEBHOOK_SECRET = secret
        transport.next_status = "action_required"
        self.payment_client._session = PaymentWinsCancel()
        self.app.dependency_overrides[webhook_provider] = lambda: self.payment_client
        try:
            owner = self._login("e2e-client-a")
            proposal_id = self.ids["client_proposal_id"]
            accepted = self.http.post(
                f"/portal/cliente/propostas/{proposal_id}/aceitar",
                headers=owner,
                json={"versao": self.ids["client_proposal_version"]},
            )
            self.assertEqual(accepted.status_code, 200, accepted.text)
            pix = self.http.post(
                f"/portal/cliente/propostas/{proposal_id}/checkout/pix",
                headers=owner,
                json={"payment_option": "entrada"},
            )
            self.assertEqual(pix.status_code, 200, pix.text)
            self.assertEqual(pix.json()["status"], "pending")
            with self.SessionLocal() as db:
                charge = db.scalar(select(CobrancaModel).where(CobrancaModel.proposta_id == proposal_id))
                payment = db.scalar(select(PagamentoModel).where(PagamentoModel.cobranca_id == charge.id))
                order_id = payment.provider_order_id
                charge_id = charge.id

            with ThreadPoolExecutor(max_workers=2) as executor:
                cancel = executor.submit(
                    self.http.post,
                    f"/portal/cliente/propostas/{proposal_id}/checkout/cancel-pix",
                    headers=owner,
                )
                self.assertTrue(cancel_started.wait(timeout=10))
                transport.change(order_id, "processed", "accredited")
                webhook = executor.submit(signed_webhook, self.http, order_id, secret)
                allow_cancel.set()
                cancel_response = cancel.result(timeout=30)
                webhook_response = webhook.result(timeout=30)

            self.assertEqual(cancel_response.status_code, 409, cancel_response.text)
            self.assertEqual(webhook_response.status_code, 200, webhook_response.text)
            self.assertEqual(webhook_response.json()["status"], "processed")
            blocked_card = self.http.post(
                f"/portal/cliente/propostas/{proposal_id}/checkout/card",
                headers=owner,
                json={
                    "payment_option": "entrada", "card_token": "synthetic-token",
                    "payment_method_id": "visa", "installments": 1,
                },
            )
            self.assertEqual(blocked_card.status_code, 409, blocked_card.text)
            with self.SessionLocal() as db:
                self.assertEqual(db.query(CobrancaModel).filter_by(proposta_id=proposal_id).count(), 1)
                self.assertEqual(db.query(PagamentoModel).filter_by(cobranca_id=charge_id).count(), 1)
                self.assertEqual(db.get(PagamentoModel, payment.id).status, "aprovado")
                proposal = db.get(PropostaModel, proposal_id)
                self.assertEqual(
                    db.query(ProducaoModel).filter_by(orcamento_id=proposal.orcamento_id).count(), 1
                )
        finally:
            allow_cancel.set()
            self.payment_client._session = previous_session
            transport.next_status = previous_status
            settings.MERCADO_PAGO_WEBHOOK_SECRET = previous_secret
            settings.COMMERCIAL_PIPELINE_V2_ENABLED = previous_v2
            if previous_webhook_override is None:
                self.app.dependency_overrides.pop(webhook_provider, None)
            else:
                self.app.dependency_overrides[webhook_provider] = previous_webhook_override

    def test_integral_checkout_policy_postgresql17(self):
        from core.config import settings
        from models import CobrancaModel, PagamentoModel, ProducaoModel, PropostaModel
        from models.enums.financeiro import PagamentoStatus
        from services import financial_service, mercado_pago_service

        previous = settings.COMMERCIAL_PIPELINE_V2_ENABLED
        settings.COMMERCIAL_PIPELINE_V2_ENABLED = True
        try:
            client_a = self._login("e2e-client-a")
            client_b = self._login("e2e-client-b")
            proposal_id = self.ids["other_client_proposal_id"]
            self.assertEqual(
                self.http.get(
                    f"/portal/cliente/propostas/{proposal_id}/checkout",
                    headers=client_a,
                ).status_code,
                404,
            )
            proposal = self.http.get(
                f"/portal/cliente/propostas/{proposal_id}",
                headers=client_b,
            )
            self.assertEqual(proposal.status_code, 200, proposal.text)
            accepted = self.http.post(
                f"/portal/cliente/propostas/{proposal_id}/aceitar",
                headers=client_b,
                json={"versao": proposal.json()["versao"]},
            )
            self.assertEqual(accepted.status_code, 200, accepted.text)

            with self.SessionLocal.begin() as db:
                charge = db.scalar(
                    select(CobrancaModel).where(CobrancaModel.proposta_id == proposal_id)
                )
                self.assertIsNotNone(charge)
                token = charge.referencia_externa
                pending = financial_service.registrar_pagamento(
                    db,
                    charge.id,
                    tipo="entrada",
                    valor=financial_service.dividir_50_50(charge.valor_total)[0],
                    status=PagamentoStatus.PENDENTE,
                    metodo="pix",
                    provider=mercado_pago_service.PROVIDER,
                    provider_reference="e2e-incompatible-pending",
                )
                pending.provider_idempotency_key = "e2e-incompatible-pending"

            public_summary = self.http.get(f"/checkout/{token}")
            self.assertEqual(public_summary.status_code, 200, public_summary.text)
            self.assertEqual(
                [option["tipo"] for option in public_summary.json()["opcoes"]],
                ["integral"],
            )
            self.assertEqual(
                self.http.post(
                    f"/checkout/{token}/pix",
                    json={"payment_option": "entrada"},
                ).status_code,
                409,
            )
            self.assertEqual(
                self.http.post(
                    f"/portal/cliente/propostas/{proposal_id}/checkout/pix",
                    headers=client_b,
                    json={"payment_option": "integral"},
                ).status_code,
                409,
            )
            with self.SessionLocal.begin() as db:
                self.assertEqual(
                    db.query(PagamentoModel)
                    .join(CobrancaModel)
                    .filter(CobrancaModel.proposta_id == proposal_id)
                    .count(),
                    1,
                )
                pending = db.scalar(
                    select(PagamentoModel)
                    .join(CobrancaModel)
                    .where(CobrancaModel.proposta_id == proposal_id)
                )
                pending.status = PagamentoStatus.CANCELADO.value

            blocked_entry = self.http.post(
                f"/checkout/{token}/pix",
                json={"payment_option": "entrada"},
            )
            self.assertEqual(blocked_entry.status_code, 409, blocked_entry.text)
            paid = self.http.post(
                f"/checkout/{token}/pix",
                json={"payment_option": "integral"},
            )
            self.assertEqual(paid.status_code, 200, paid.text)
            self.assertEqual(paid.json()["status"], "approved")

            with self.SessionLocal() as db:
                proposal_model = db.get(PropostaModel, proposal_id)
                self.assertEqual(
                    db.query(ProducaoModel)
                    .filter(ProducaoModel.orcamento_id == proposal_model.orcamento_id)
                    .count(),
                    1,
                )
                self.assertEqual(
                    db.query(PagamentoModel)
                    .join(CobrancaModel)
                    .filter(CobrancaModel.proposta_id == proposal_id)
                    .count(),
                    2,
                )
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
            "E2E_ADMIN_POLICY_BUDGET_ID": str(self.ids["admin_policy_budget_id"]),
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
            policy_proposal = db.get(PropostaModel, self.ids["admin_policy_proposal_id"])
            self.assertEqual(policy_proposal.politica_pagamento, "entrada_50_50")
            self.assertGreaterEqual(policy_proposal.versao, 3)
            self.assertEqual(
                db.query(ProducaoModel)
                .filter(ProducaoModel.orcamento_id == proposal.orcamento_id)
                .count(),
                1,
            )


if __name__ == "__main__":
    unittest.main()
