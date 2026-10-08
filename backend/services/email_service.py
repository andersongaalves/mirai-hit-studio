import base64
import logging
from datetime import datetime
from pathlib import Path

import resend
from core.config import settings
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

resend.api_key = settings.RESEND_API_KEY
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

templates = Environment(
    loader=FileSystemLoader(BASE_DIR / "templates"),
    autoescape=select_autoescape(["html"]),
)


class EmailService:

    @classmethod
    def enviar_convite_cliente(cls, cliente, activation_url: str, *, idempotency_key: str):
        html = cls.render(
            "email_convite_cliente.html",
            nome=cliente.nome,
            activation_url=activation_url,
        )
        return resend.Emails.send({
            "from": settings.EMAIL_FROM,
            "to": cliente.email,
            "subject": "Ative seu acesso ao Portal Mirai",
            "html": html,
        }, {"idempotency_key": idempotency_key})

    @classmethod
    def enviar_proposta_disponivel(
        cls,
        cliente,
        proposal_url: str,
        *,
        proposta_numero: str,
        idempotency_key: str,
    ):
        html = cls.render(
            "email_proposta_portal.html",
            nome=cliente.nome,
            proposal_url=proposal_url,
            proposta_numero=proposta_numero,
        )
        return resend.Emails.send({
            "from": settings.EMAIL_FROM,
            "to": cliente.email,
            "subject": f"Proposta {proposta_numero} disponivel no Portal Mirai",
            "html": html,
        }, {"idempotency_key": idempotency_key})

    @classmethod
    def enviar_confirmacao_cadastro(
        cls,
        cliente,
        activation_url: str,
        *,
        idempotency_key: str,
    ):
        html = cls.render(
            "email_confirmacao_cadastro.html",
            nome=cliente.nome,
            activation_url=activation_url,
        )
        return resend.Emails.send({
            "from": settings.EMAIL_FROM,
            "to": cliente.email,
            "subject": "Confirme sua conta Mirai Hit Studio",
            "html": html,
        }, {"idempotency_key": idempotency_key})

    @classmethod
    def enviar_recuperacao_senha(
        cls,
        cliente,
        recovery_url: str,
        *,
        idempotency_key: str,
    ):
        html = cls.render(
            "email_recuperacao_senha.html",
            nome=cliente.nome,
            recovery_url=recovery_url,
            validity_minutes=60,
        )
        return resend.Emails.send({
            "from": settings.EMAIL_FROM,
            "to": cliente.email,
            "subject": "Redefina sua senha da Mirai Hit Studio",
            "html": html,
        }, {"idempotency_key": idempotency_key})

    @classmethod
    def enviar_proposta(cls, proposta, pdf, valor):
        cliente = proposta.cliente_snapshot.cliente
        html = cls.render("email_proposta.html", nome=cliente.nome, numero=proposta.numero,
                          resumo=proposta.objeto or proposta.descricao[:300], valor=valor)
        return resend.Emails.send({
            "from": settings.EMAIL_FROM, "to": cliente.email,
            "subject": f"Proposta comercial {proposta.numero} - Mirai Hit Studio",
            "html": html,
            "attachments": [{"filename": f"proposta-{proposta.id}-v{proposta.versao}.pdf",
                             "content": base64.b64encode(pdf).decode("ascii")}],
        }, {"idempotency_key": f"proposal/{proposta.id}/v{proposta.versao}/{proposta.created_at.isoformat()}"})

    @staticmethod
    def render(template_name: str, **context):

        context["ano"] = datetime.now().year

        template = templates.get_template(template_name)

        return template.render(**context)

    @staticmethod
    def enviar(destino: str, assunto: str, html: str, texto: str | None = None):

        try:
            payload = {
                "from": settings.EMAIL_FROM,
                "to": destino,
                "subject": assunto,
                "html": html,
            }
            if texto:
                payload["text"] = texto
            return resend.Emails.send(payload)

        except Exception:

            logger.error("email_send_failed")

            return None

    @classmethod
    def enviar_confirmacao(cls, orcamento, protocolo):

        html = cls.render(
            "email_cliente.html",
            protocolo=protocolo,
            nome=orcamento.nome_cliente,
            servico=orcamento.servico,
            valor=f"{orcamento.valor_total:.2f}" if orcamento.valor_total is not None else "A definir",
            data=orcamento.data_solicitacao.strftime("%d/%m/%Y %H:%M"),
            observacoes=orcamento.detalhes,
        )

        return cls.enviar(
            destino=orcamento.email,
            assunto=f"Recebemos seu orçamento • {protocolo}",
            html=html,
        )

    @classmethod
    def enviar_notificacao_admin(cls, orcamento, protocolo):

        html = cls.render(
            "email_admin.html",
            protocolo=protocolo,
            nome=orcamento.nome_cliente,
            email=orcamento.email,
            telefone=orcamento.whatsapp,
            servico=orcamento.servico,
            valor=f"{orcamento.valor_total:.2f}" if orcamento.valor_total is not None else "A definir",
            data=orcamento.data_solicitacao.strftime("%d/%m/%Y %H:%M"),
            observacoes=orcamento.detalhes,
        )

        return cls.enviar(
            destino=settings.ADMIN_EMAIL,
            assunto=f"Novo orçamento • {protocolo}",
            html=html,
        )

    @classmethod
    def _url_cancelamento(cls, token: str):
        base_url = getattr(settings, "PUBLIC_API_URL", "http://localhost:8000").rstrip("/")
        return f"{base_url}/newsletter/unsubscribe?token={token}"

    @staticmethod
    def _texto_para_html(texto: str):
        lines = [escape(line) if line else Markup("&nbsp;") for line in texto.splitlines()]
        return Markup("<br />").join(lines)

    @classmethod
    def enviar_newsletter(cls, subscriber, campaign):
        unsubscribe_url = cls._url_cancelamento(subscriber.unsubscribe_token)
        html = cls.render(
            "email_campaign.html",
            preview_text=campaign.preview_text,
            body_html=cls._texto_para_html(campaign.body_text),
            unsubscribe_url=unsubscribe_url,
        )
        return cls.enviar(
            destino=subscriber.email,
            assunto=campaign.assunto,
            html=html,
            texto=f"{campaign.body_text}\n\nCancelar inscricao: {unsubscribe_url}",
        )

    @classmethod
    def enviar_boas_vindas(cls, subscriber):

        html = cls.render(
            "email_newsletter.html",
            nome=subscriber.nome or subscriber.email.split("@")[0].replace(".", " ").title(),
            unsubscribe_url=cls._url_cancelamento(subscriber.unsubscribe_token),
        )

        return cls.enviar(
            destino=subscriber.email, assunto="🎵 Bem-vindo à Mirai Hit Studio!", html=html
        )
