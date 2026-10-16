"""One escaped HTML template for browser preview and PDF conversion."""
import base64
import unicodedata
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from textwrap import wrap

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from xhtml2pdf import pisa

from models.enums.proposta import PoliticaPagamento
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
BRASILIA = timezone(timedelta(hours=-3))


# Defaults of older proposals; the standard conditions now live in the template itself.
CONDICOES_LEGADAS = {
    "Esta proposta contempla os servi\u00e7os descritos neste documento.\n\n"
    "Altera\u00e7\u00f5es de escopo poder\u00e3o gerar revis\u00e3o de valores e prazos.\n\n"
    "O in\u00edcio da produ\u00e7\u00e3o ocorre ap\u00f3s confirma\u00e7\u00e3o da condi\u00e7\u00e3o de pagamento "
    "definida nesta proposta e envio dos materiais necess\u00e1rios.",
}


def _sem_emoji(texto: str) -> str:
    """The PDF font has no emoji glyphs; catalog names like "🎛️ Mixagem" print without them."""
    limpo = "".join(c for c in str(texto) if unicodedata.category(c) != "So" and c not in "\ufe0f\u200d")
    return " ".join(limpo.split())


def _plural(n, um, varios):
    return f"{n} {um if n == 1 else varios}"


def _incluido(snapshot) -> list[dict]:
    """'What is included' per contracted catalog service, from the frozen contract (5.05/5.09)."""
    linhas = []
    for item in (getattr(snapshot, "itens", None) or []):
        if item.componentes:
            servicos = [(componente.servico_nome, componente.cotas_arquivos or [],
                         [etapa for etapa in item.etapas if etapa.componente_indice == componente.indice])
                        for componente in item.componentes]
        elif item.servico_id is not None:
            servicos = [(item.servico_nome or item.descricao, item.cotas_arquivos or [], item.etapas)]
        else:
            continue
        for nome, cotas, etapas in servicos:
            detalhes = []
            material = next((cota for cota in cotas if cota.tipo == "material"), None)
            if material is not None and material.max_arquivos:
                detalhes.append("até " + _plural(material.max_arquivos, "faixa", "faixas"))
            if material is not None and getattr(material, "max_duracao_min", None):
                detalhes.append(f"até {material.max_duracao_min} min por faixa")
            revisoes = [etapa.revisoes_incluidas for etapa in etapas if etapa.revisoes_incluidas is not None]
            if revisoes:
                total = sum(revisoes)
                detalhes.append("sem revisões incluídas" if total == 0
                                else _plural(total, "revisão incluída", "revisões incluídas"))
            servico = _sem_emoji(nome or "") or "Serviço"
            if Decimal(str(item.quantidade)) != 1:
                quantidade = format(Decimal(str(item.quantidade)).normalize(), "f")
                servico = f"{servico} (×{quantidade})"
            linhas.append({"servico": servico, "detalhes": "; ".join(detalhes)})
    return linhas


def _prazo_dias(snapshot) -> int | None:
    """Stages run one after the other (5.06), so the delivery deadline is the sum of their days."""
    total = sum(etapa.prazo_dias or 0 for item in (getattr(snapshot, "itens", None) or []) for etapa in item.etapas)
    return total or None


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
        politica_pagamento = {
            PoliticaPagamento.INTEGRAL: "Pagamento integral",
            PoliticaPagamento.ENTRADA_50_50: "Entrada de 50% + saldo de 50%",
        }[PoliticaPagamento(proposta.politica_pagamento)]
        logo = "data:image/png;base64," + base64.b64encode(
            (ROOT / "frontend" / "assets" / "logo_proposta.png").read_bytes()).decode("ascii")
        snapshot = getattr(proposta, "snapshot_economico", None)
        condicoes = (proposta.condicoes or "").strip()
        # Emission date: when it was sent, or today for previews and the PDF generated at sending.
        emissao = (getattr(proposta, "enviada_em", None) or datetime.now(timezone.utc)).astimezone(BRASILIA)
        return TEMPLATES.get_template("proposta.html").render(
            proposta=proposta, cliente=cliente, produtor=produtor, itens=itens,
            totais=totais, pagamentos=pagamentos, politica_pagamento=politica_pagamento,
            politica=PoliticaPagamento(proposta.politica_pagamento).value,
            produtor_credito=produtor if produtor and produtor != "Nao definido" else "Mirai Hit Studio",
            incluido=_incluido(snapshot), prazo_dias=_prazo_dias(snapshot),
            condicoes_especificas="" if condicoes in CONDICOES_LEGADAS else condicoes,
            data_emissao=emissao.strftime("%d/%m/%Y") if emissao else "-",
            logo=logo)
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
