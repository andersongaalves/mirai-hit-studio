"""Beat license contracts (lease and exclusive), released with the files after payment.

The PDF is rendered on demand from the license record, so the client can download
it again at any time from the purchased beat.
"""
import base64

from models import BeatLicencaModel, BeatModel, ClienteModel, PropostaModel, UsuarioModel
from services.documento_storage import DocumentoIndisponivel
from services.pdf_service import BRASILIA, ROOT, TEMPLATES, gerar_pdf

# Business terms of the non-exclusive (lease) license; reviewed by the studio.
LIMITES_LEASE = {
    "streams": "500.000",
    "vendas": "5.000",
    "videos": "1",
    "visualizacoes": "500.000",
    "radio": "permitida em até 2 emissoras",
}

ROTULOS = {
    "lease": "Lease MP3",
    "lease_mp3": "Lease MP3",
    "lease_wav": "Lease WAV",
    "multitrack": "Lease Multitrack (stems)",
    "exclusivo": "Exclusiva",
}

FORMATOS = {
    "lease": "MP3",
    "lease_mp3": "MP3",
    "lease_wav": "WAV",
    "multitrack": "MP3, WAV e multitrack (stems)",
    "exclusivo": "MP3, WAV e multitrack (stems)",
}


class ContratoNaoEncontrado(Exception):
    pass


def _license(db, licenca_id, cliente_id=None):
    license = db.get(BeatLicencaModel, licenca_id)
    if (
        license is None
        or license.status != "adquirida"
        or license.adquirida_em is None
        or (cliente_id is not None and license.cliente_id != cliente_id)
    ):
        raise ContratoNaoEncontrado("Contrato não encontrado.")
    return license


def gerar(db, licenca_id, *, cliente_id=None):
    """Returns (pdf_bytes, filename). cliente_id restricts to the owner (client portal)."""
    from services.beat_service import _download_name

    license = _license(db, licenca_id, cliente_id)
    beat = db.get(BeatModel, license.beat_id)
    client = db.get(ClienteModel, license.cliente_id)
    proposal = db.get(PropostaModel, license.proposta_id)
    producer = db.get(UsuarioModel, beat.produtor_id) if beat is not None else None
    if beat is None or client is None:
        raise ContratoNaoEncontrado("Contrato não encontrado.")
    producer_name = (getattr(producer, "nome_exibicao", None) or getattr(producer, "username", None) or "Mirai Hit Studio")
    # The beatmaker CPF identifies the licensor; it appears only in this private contract.
    cpf = getattr(producer, "cpf", None) or ""
    producer_cpf = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}" if len(cpf) == 11 and cpf.isdigit() else None
    try:
        logo = "data:image/png;base64," + base64.b64encode(
            (ROOT / "frontend" / "assets" / "logo_proposta.png").read_bytes()).decode("ascii")
        html = TEMPLATES.get_template("contrato_beat.html").render(
            numero=f"MHS-BEAT-{license.id:06d}",
            data=license.adquirida_em.astimezone(BRASILIA).strftime("%d/%m/%Y"),
            proposta_numero=getattr(proposal, "numero", "-") or "-",
            exclusivo=license.tipo == "exclusivo",
            licenca_rotulo=ROTULOS.get(license.tipo, license.tipo),
            formatos=FORMATOS.get(license.tipo, "-"),
            valor=license.valor,
            beat_titulo=beat.titulo,
            produtor=producer_name,
            produtor_cpf=producer_cpf,
            cliente_nome=client.nome,
            cliente_email=client.email or "-",
            limites=LIMITES_LEASE,
            logo=logo,
        )
    except Exception:
        raise DocumentoIndisponivel("Não foi possível montar o contrato.") from None
    filename = _download_name(beat, f"-contrato-{license.tipo.replace('_', '-')}", "pdf")
    return gerar_pdf(html), filename
