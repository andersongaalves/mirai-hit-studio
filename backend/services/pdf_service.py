"""One escaped HTML template for browser preview and PDF conversion."""
import base64
from io import BytesIO
from pathlib import Path
from textwrap import wrap

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from xhtml2pdf import pisa

from services.documento_storage import DocumentoIndisponivel
from services.proposta_service import PropostaInvalida, calcular_totais
from services.qr_code_service import gerar_qr_code

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = Environment(loader=FileSystemLoader(ROOT / "backend" / "templates"),
                        autoescape=select_autoescape(["html"]), undefined=StrictUndefined)


def moeda(value):
    return "R$ " + format(value, ",.2f").replace(",", "_").replace(".", ",").replace("_", ".")


def linhas(text, width=85):
    # Bound individual blocks/cells so long unbroken input also fits printed pages.
    return [line for paragraph in str(text).splitlines() for line in (wrap(paragraph, width) or [""])]


TEMPLATES.filters.update(moeda=moeda, linhas=linhas)


def renderizar_html(proposta, produtor="Nao definido", final=False):
    cliente = proposta.cliente_snapshot.cliente
    if not proposta.numero.strip() or not cliente.nome.strip() or not cliente.email.strip():
        raise PropostaInvalida("Numero e dados do cliente sao obrigatorios para o documento.")
    if final and not proposta.itens:
        raise PropostaInvalida("Adicione pelo menos um item antes de gerar o PDF.")
    if any(not item.descricao.strip() for item in proposta.itens):
        raise PropostaInvalida("Preencha a descricao de todos os itens.")
    if len({payment.tipo for payment in proposta.pagamentos}) != len(proposta.pagamentos):
        raise PropostaInvalida("Existem tipos de pagamento duplicados.")
    pagamentos = []
    for payment in proposta.pagamentos:
        if not payment.habilitado:
            continue
        try:
            qr = gerar_qr_code(payment.url)
        except ValueError as error:
            raise PropostaInvalida(str(error)) from None
        pagamentos.append({"titulo": payment.titulo, "url": payment.url, "qr": qr})
    totais = calcular_totais(proposta.itens)
    itens = []
    for item in proposta.itens:
        total = calcular_totais([item])
        itens.append({"item": item, "partes": wrap(item.descricao, 240) or [""], "total": total})
    try:
        logo = "data:image/png;base64," + base64.b64encode(
            (ROOT / "frontend" / "assets" / "logo_mirai_BnW.png").read_bytes()).decode("ascii")
        return TEMPLATES.get_template("proposta.html").render(
            proposta=proposta, cliente=cliente, produtor=produtor, itens=itens,
            totais=totais, pagamentos=pagamentos, logo=logo)
    except Exception:
        raise DocumentoIndisponivel("Nao foi possivel renderizar o template da proposta.") from None


def _recurso_local(uri, relative):
    # The controlled template embeds all images. Forbid network/filesystem resources.
    if not uri.startswith("data:image/png;base64,"):
        raise DocumentoIndisponivel("Recurso externo bloqueado no documento.")
    return uri


def gerar_pdf(html):
    output = BytesIO()
    try:
        result = pisa.CreatePDF(html, dest=output, encoding="utf-8", link_callback=_recurso_local)
        if result.err or result.warn or not output.getvalue().startswith(b"%PDF-"):
            raise ValueError()
    except Exception:
        raise DocumentoIndisponivel("Nao foi possivel converter o documento em PDF.") from None
    return output.getvalue()
