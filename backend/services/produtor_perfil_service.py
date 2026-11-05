"""Public producer pages (/produtores/<endereço>).

Each producer has a page with what they customise (photo, cover, short line, bio, city,
accent colour, links, first tab) and what comes from their work: projects in the Mirai
portfolio they are credited on, projects delivered at Mirai, and their beats. Nothing
private (login, e-mail, CPF, values) is ever shown.

Every producer has an address from the start, without a database row: "<name>-<id>".
A producer may choose a shorter one; the original keeps working and points to it.
"""
import re
import unicodedata
from urllib.parse import urlsplit

from fastapi import HTTPException
from models import (
    BeatModel,
    OrcamentoModel,
    ProducaoEtapaModel,
    ProducaoModel,
    ProdutorPerfilModel,
    ProjetoCreditoModel,
    ProjetoModel,
    UsuarioModel,
)
from services import audit_service
from services.portfolio_service import PUBLIC_CASE_TYPES, PUBLIC_VERTICALS
from services.storage.contracts import (
    StorageError,
    StorageScope,
    StorageValidationError,
)
from services.storage.policies import DEFAULT_POLICIES
from services.storage.registry import storage_for
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

FINAIS = ("finalizado", "entregue")
ABAS = ("portfolio", "beats")
# Accent colours that read well on the site's dark background.
CORES = ("#00d5ed", "#cb32e6", "#ff5c8a", "#ffb547", "#7ee081", "#6c8cff", "#ff7a45", "#f5f7fa")
# Links a producer can show, and the sites each one may point to.
LINKS = {
    "instagram": ("instagram.com",),
    "youtube": ("youtube.com", "youtu.be"),
    "spotify": ("open.spotify.com", "spotify.com"),
    "soundcloud": ("soundcloud.com",),
    "tiktok": ("tiktok.com",),
    "beatstars": ("beatstars.com",),
    "site": None,
}
IMAGENS = {"foto": 5 * 1024 * 1024, "capa": 8 * 1024 * 1024}
RESERVADOS = frozenset({
    "admin", "api", "beats", "cliente", "clientes", "produtor", "produtores", "perfil", "mirai",
    "novo", "editar", "configuracoes", "suporte", "contato",
})
SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$")
SLUG_PADRAO = re.compile(r"-(\d+)$")


class PerfilInvalido(HTTPException):
    def __init__(self, detail):
        super().__init__(422, detail)


def _texto(value):
    return " ".join(str(value).split()) if value is not None else ""


def slugify(value):
    text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:28].strip("-")


def nome_publico(usuario):
    return (usuario.nome_exibicao or usuario.username or "Produtor").strip()


def slug_padrao(usuario):
    return f"{slugify(nome_publico(usuario)) or 'produtor'}-{usuario.id}"


def _visivel(usuario):
    return usuario is not None and usuario.role == "produtor" and usuario.ativo and not usuario.is_test


def slugs(db, ids):
    """The address of each producer's page (chosen or original), for links."""
    ids = {item for item in ids if item is not None}
    if not ids:
        return {}
    chosen = dict(db.execute(
        select(ProdutorPerfilModel.usuario_id, ProdutorPerfilModel.slug).where(ProdutorPerfilModel.usuario_id.in_(ids))
    ).all())
    users = db.scalars(select(UsuarioModel).where(UsuarioModel.id.in_(ids))).all()
    return {user.id: chosen.get(user.id) or slug_padrao(user) for user in users if _visivel(user)}


def _resolver(db, slug):
    slug = (slug or "").strip().lower()[:60]
    perfil = db.scalar(select(ProdutorPerfilModel).where(ProdutorPerfilModel.slug == slug))
    usuario = db.get(UsuarioModel, perfil.usuario_id) if perfil else None
    if usuario is None:
        match = SLUG_PADRAO.search(slug)
        usuario = db.get(UsuarioModel, int(match.group(1))) if match and len(match.group(1)) <= 9 else None
        perfil = db.get(ProdutorPerfilModel, usuario.id) if usuario is not None else None
        # The original address only works with the producer's own name in it.
        if usuario is not None and slug != slug_padrao(usuario):
            usuario = None
    if not _visivel(usuario):
        raise HTTPException(404, "Produtor não encontrado.")
    return usuario, perfil


def _metricas(db, usuario_id):
    portfolio = db.scalar(
        select(func.count(func.distinct(ProjetoModel.id)))
        .join(ProjetoCreditoModel, ProjetoCreditoModel.projeto_id == ProjetoModel.id)
        .where(ProjetoCreditoModel.usuario_id == usuario_id,
               ProjetoModel.vertical.in_(PUBLIC_VERTICALS), ProjetoModel.case_type.in_(PUBLIC_CASE_TYPES))
    ) or 0
    teste = select(OrcamentoModel.id).where(OrcamentoModel.is_test.is_(True))
    responsavel = select(ProducaoEtapaModel.producao_id).where(ProducaoEtapaModel.responsavel_usuario_id == usuario_id)
    mirai = db.scalar(
        select(func.count(func.distinct(ProducaoModel.id)))
        .where(or_(ProducaoModel.produtor_id == usuario_id, ProducaoModel.id.in_(responsavel)),
               ProducaoModel.status.in_(FINAIS),
               or_(ProducaoModel.orcamento_id.is_(None), ~ProducaoModel.orcamento_id.in_(teste)))
    ) or 0
    return {"portfolio": portfolio, "mirai": mirai}


FUNCOES = {
    "producao": "Produção", "mixagem": "Mixagem", "masterizacao": "Masterização", "composicao": "Composição",
    "gravacao": "Gravação", "beat": "Beat",
}


def _portfolio(db, usuario_id):
    rows = db.execute(
        select(ProjetoModel, ProjetoCreditoModel)
        .join(ProjetoCreditoModel, ProjetoCreditoModel.projeto_id == ProjetoModel.id)
        .where(ProjetoCreditoModel.usuario_id == usuario_id,
               ProjetoModel.vertical.in_(PUBLIC_VERTICALS), ProjetoModel.case_type.in_(PUBLIC_CASE_TYPES))
        .order_by(ProjetoModel.destaque.desc(), ProjetoModel.id.desc())
    ).all()
    projetos = {}
    for projeto, credito in rows:
        item = projetos.setdefault(projeto.id, {
            "id": projeto.id, "titulo": projeto.titulo, "artista": projeto.artista, "categoria": projeto.categoria,
            "descricao": projeto.descricao, "vertical": projeto.vertical, "case_type": projeto.case_type,
            "segmentos_json": projeto.segmentos_json or [], "link_audio": projeto.link_audio,
            "link_capa": projeto.link_capa, "funcoes": [],
        })
        funcao = credito.funcao_outra if credito.funcao == "outra" else FUNCOES.get(credito.funcao, credito.funcao)
        if funcao and funcao not in item["funcoes"]:
            item["funcoes"].append(funcao)
    return list(projetos.values())


def _links(perfil):
    links = (perfil.links_json if perfil else None) or {}
    return {key: links[key] for key in LINKS if isinstance(links.get(key), str) and links[key]}


def _base(usuario, perfil):
    especialidades = [item for item in (usuario.especialidades or "").split(",") if item]
    return {
        "slug": (perfil.slug if perfil else None) or slug_padrao(usuario),
        "nome": nome_publico(usuario),
        "headline": perfil.headline if perfil else None,
        "bio": perfil.bio if perfil else None,
        "cidade": perfil.cidade if perfil else None,
        "foto_url": perfil.foto_url if perfil else None,
        "capa_url": perfil.capa_url if perfil else None,
        "cor": (perfil.cor if perfil else None) or CORES[0],
        "links": _links(perfil),
        "aba_inicial": (perfil.aba_inicial if perfil else None) or "portfolio",
        "especialidades": especialidades,
    }


def publico(db, slug):
    from services import beat_service

    usuario, perfil = _resolver(db, slug)
    portfolio = _portfolio(db, usuario.id)
    beats = beat_service.client_list(db, produtor_id=usuario.id)
    metricas = _metricas(db, usuario.id)
    metricas["beats"] = sum(1 for beat in beats if not beat.get("vendido"))
    metricas["total"] = metricas["portfolio"] + metricas["mirai"]
    return {**_base(usuario, perfil), "metricas": metricas, "portfolio": portfolio, "beats": beats}


def meu(db, usuario):
    perfil = db.get(ProdutorPerfilModel, usuario.id)
    data = _base(usuario, perfil)
    data["slug_padrao"] = slug_padrao(usuario)
    data["cores"] = list(CORES)
    data["redes"] = list(LINKS)
    data["metricas"] = _metricas(db, usuario.id)
    data["beats"] = db.scalar(select(func.count(BeatModel.id)).where(
        BeatModel.produtor_id == usuario.id, BeatModel.status == "aprovado", BeatModel.ativo.is_(True))) or 0
    return data


def _garantir(db, usuario):
    perfil = db.get(ProdutorPerfilModel, usuario.id)
    if perfil is None:
        perfil = ProdutorPerfilModel(usuario_id=usuario.id, slug=slug_padrao(usuario), links_json={})
        db.add(perfil)
    return perfil


def _validar_slug(db, usuario, slug):
    slug = (slug or "").strip().lower()
    if slug == slug_padrao(usuario):
        return slug
    if not SLUG.fullmatch(slug) or "--" in slug:
        raise PerfilInvalido("Use de 3 a 40 letras minúsculas, números ou hífens, sem hífen no começo ou no fim.")
    if slug in RESERVADOS or SLUG_PADRAO.search(slug):
        raise PerfilInvalido("Este endereço não está disponível. Escolha outro (sem número no final).")
    other = db.scalar(select(ProdutorPerfilModel.usuario_id).where(ProdutorPerfilModel.slug == slug))
    if other is not None and other != usuario.id:
        raise PerfilInvalido("Este endereço já é usado por outro produtor.")
    return slug


def _validar_link(chave, valor):
    valor = (valor or "").strip()
    if not valor:
        return None
    if len(valor) > 300:
        raise PerfilInvalido("Cada link pode ter até 300 caracteres.")
    parts = urlsplit(valor)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host or parts.username or parts.password:
        raise PerfilInvalido("Os links precisam começar com https://.")
    sites = LINKS[chave]
    if sites and not any(host == site or host.endswith("." + site) for site in sites):
        raise PerfilInvalido(f"O link de {chave} precisa ser de {', '.join(sites)}.")
    return valor


def atualizar(db, usuario, dados, request_id=None):
    perfil = _garantir(db, usuario)
    campos = dados.model_dump(exclude_unset=True)
    if "slug" in campos:
        perfil.slug = _validar_slug(db, usuario, campos["slug"])
    for campo, limite in (("headline", 120), ("cidade", 80)):
        if campo in campos:
            valor = _texto(campos[campo])[:limite]
            setattr(perfil, campo, valor or None)
    if "bio" in campos:
        bio = (campos["bio"] or "").strip()
        if len(bio) > 1500:
            raise PerfilInvalido("A bio pode ter até 1.500 caracteres.")
        perfil.bio = bio or None
    if "cor" in campos:
        cor = (campos["cor"] or "").lower() or None
        if cor is not None and cor not in CORES:
            raise PerfilInvalido("Escolha uma das cores disponíveis.")
        perfil.cor = cor
    if "aba_inicial" in campos:
        if campos["aba_inicial"] not in ABAS:
            raise PerfilInvalido("Aba inicial inválida.")
        perfil.aba_inicial = campos["aba_inicial"]
    if "links" in campos:
        links = campos["links"] or {}
        desconhecidos = set(links) - set(LINKS)
        if desconhecidos:
            raise PerfilInvalido("Rede não suportada.")
        perfil.links_json = {chave: valor for chave in LINKS if (valor := _validar_link(chave, links.get(chave)))}
    audit_service.record(db, actor=usuario, action="producer.profile_updated", entity_type="user",
                         entity_id=usuario.id, metadata={"campos": sorted(campos)}, request_id=request_id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise PerfilInvalido("Este endereço já é usado por outro produtor.") from None
    return meu(db, usuario)


def salvar_imagem(db, usuario, tipo, data, content_type, request_id=None):
    if tipo not in IMAGENS:
        raise HTTPException(404, "Imagem não encontrada.")
    if len(data) > IMAGENS[tipo]:
        raise HTTPException(413, f"A imagem pode ter até {IMAGENS[tipo] // (1024 * 1024)} MB.")
    try:
        DEFAULT_POLICIES[StorageScope.PUBLIC_IMAGE].validate(data, content_type)
    except StorageValidationError:
        raise PerfilInvalido("Envie uma imagem JPG, PNG ou WebP.") from None
    storage = storage_for(StorageScope.PUBLIC_IMAGE)
    try:
        saved = storage.save(data, content_type)
    except StorageError:
        raise HTTPException(503, "Não foi possível guardar a imagem agora.") from None
    perfil = _garantir(db, usuario)
    anterior = getattr(perfil, f"{tipo}_ref")
    setattr(perfil, f"{tipo}_url", saved.public_url or storage.get_public_url(saved.reference))
    setattr(perfil, f"{tipo}_ref", str(saved.reference))
    audit_service.record(db, actor=usuario, action="producer.profile_image_updated", entity_type="user",
                         entity_id=usuario.id, metadata={"tipo": tipo}, request_id=request_id)
    try:
        db.commit()
    except Exception:
        db.rollback()
        _apagar(storage, str(saved.reference))
        raise
    _apagar(storage, anterior)
    return meu(db, usuario)


def remover_imagem(db, usuario, tipo, request_id=None):
    if tipo not in IMAGENS:
        raise HTTPException(404, "Imagem não encontrada.")
    perfil = db.get(ProdutorPerfilModel, usuario.id)
    if perfil is None or not getattr(perfil, f"{tipo}_url"):
        return meu(db, usuario)
    anterior = getattr(perfil, f"{tipo}_ref")
    setattr(perfil, f"{tipo}_url", None)
    setattr(perfil, f"{tipo}_ref", None)
    audit_service.record(db, actor=usuario, action="producer.profile_image_removed", entity_type="user",
                         entity_id=usuario.id, metadata={"tipo": tipo}, request_id=request_id)
    db.commit()
    _apagar(storage_for(StorageScope.PUBLIC_IMAGE), anterior)
    return meu(db, usuario)


def _apagar(storage, referencia):
    if not referencia:
        return
    try:
        storage.delete(referencia)
    except StorageError:
        pass  # An orphan public image is harmless; the profile no longer points to it.
