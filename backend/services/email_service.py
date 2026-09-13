from pathlib import Path
from datetime import datetime
import base64
import logging

import resend

from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.config import settings

resend.api_key = settings.RESEND_API_KEY
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

templates = Environment(
    loader=FileSystemLoader(BASE_DIR / "templates"),
    autoescape=select_autoescape(["html"]),
)


class EmailService:

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
    def enviar(destino: str, assunto: str, html: str):

        try:
            return resend.Emails.send(
                {
                    "from": settings.EMAIL_FROM,
                    "to": destino,
                    "subject": assunto,
                    "html": html,
                }
            )

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
            valor=f"{orcamento.valor_total:.2f}",
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
            valor=f"{orcamento.valor_total:.2f}",
            data=orcamento.data_solicitacao.strftime("%d/%m/%Y %H:%M"),
            observacoes=orcamento.detalhes,
        )

        return cls.enviar(
            destino=settings.ADMIN_EMAIL,
            assunto=f"Novo orçamento • {protocolo}",
            html=html,
        )

    @classmethod
    def enviar_boas_vindas(cls, email: str):

        html = cls.render(
            "email_newsletter.html", nome=email.split("@")[0].replace(".", " ").title()
        )

        return cls.enviar(
            destino=email, assunto="🎵 Bem-vindo à Mirai Hit Studio!", html=html
        )
