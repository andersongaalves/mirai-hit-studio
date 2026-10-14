"""Per-production message thread (Roadmap 3.0, 5.03).

Messages are immutable. Clients only see and write messages addressed to everyone;
producers and admins may also exchange internal team notes. Ownership and file
visibility are always checked on the server.
"""

from sqlalchemy.orm import Session

from crud import crud_producao
from models import OrcamentoModel, ProducaoArquivoModel, ProducaoMensagemModel, ProducaoModel

MAX_TEXT_LENGTH = 2000
ROLES = ("cliente", "produtor", "admin")


class MensagemError(Exception):
    pass


class MensagemNotFound(MensagemError):
    pass


class MensagemInvalida(MensagemError):
    pass


def production_for(db: Session, role: str, production_id: int, user) -> ProducaoModel:
    query = db.query(ProducaoModel).filter(ProducaoModel.id == production_id)
    if role == "cliente":
        query = query.join(OrcamentoModel, ProducaoModel.orcamento_id == OrcamentoModel.id).filter(
            OrcamentoModel.cliente_id == user.cliente_id
        )
    elif role == "produtor":
        query = query.filter(crud_producao.acesso_produtor(user.id))  # 5.07: coordinator or stage owner.
    elif role != "admin":
        raise MensagemNotFound("Producao nao encontrada.")
    production = query.first()
    if production is None:
        raise MensagemNotFound("Producao nao encontrada.")
    return production


def _file_visible(role: str, model: ProducaoArquivoModel) -> bool:
    if role == "admin":
        return True
    if role == "produtor":
        return bool(model.visivel_produtor)
    return bool(model.visivel_cliente) and model.tipo != "comprovante"


def _message_visible(role: str, model: ProducaoMensagemModel) -> bool:
    return role != "cliente" or model.audiencia == "todos"


def _clean_text(text: str) -> str:
    cleaned = "".join(
        character for character in text
        if character in "\n\t" or (ord(character) >= 32 and ord(character) != 127)
    ).strip()
    if not cleaned:
        raise MensagemInvalida("Escreva uma mensagem.")
    if len(cleaned) > MAX_TEXT_LENGTH:
        raise MensagemInvalida(f"A mensagem deve ter ate {MAX_TEXT_LENGTH} caracteres.")
    return cleaned


def _serialize(role: str, viewer_id: int, model: ProducaoMensagemModel, files: dict, visible_ids: set):
    linked = files.get(model.arquivo_id)
    return {
        "id": model.id,
        "producao_id": model.producao_id,
        "autor_papel": model.autor_papel,
        "enviado_por_mim": model.autor_usuario_id == viewer_id,
        "audiencia": model.audiencia,
        "texto": model.texto,
        # A reply to something the viewer cannot see is shown without the reference.
        "responde_a_id": model.responde_a_id if model.responde_a_id in visible_ids else None,
        "arquivo": (
            {"id": linked.id, "nome_exibicao": linked.nome_exibicao, "tipo": linked.tipo, "versao": linked.versao}
            if linked is not None and _file_visible(role, linked)
            else None
        ),
        "created_at": model.created_at,
    }


def list_messages(db: Session, production: ProducaoModel, *, role: str, user) -> list[dict]:
    query = db.query(ProducaoMensagemModel).filter(ProducaoMensagemModel.producao_id == production.id)
    if role == "cliente":
        query = query.filter(ProducaoMensagemModel.audiencia == "todos")
    rows = query.order_by(ProducaoMensagemModel.created_at.asc(), ProducaoMensagemModel.id.asc()).all()
    file_ids = {row.arquivo_id for row in rows if row.arquivo_id}
    files = {
        item.id: item
        for item in db.query(ProducaoArquivoModel).filter(ProducaoArquivoModel.id.in_(file_ids)).all()
    } if file_ids else {}
    visible_ids = {row.id for row in rows}
    return [_serialize(role, user.id, row, files, visible_ids) for row in rows]


def post_message(
    db: Session,
    production: ProducaoModel,
    *,
    role: str,
    user,
    texto: str,
    audiencia: str = "todos",
    responde_a_id: int | None = None,
    arquivo_id: int | None = None,
) -> dict:
    if role not in ROLES:
        raise MensagemInvalida("Papel invalido.")
    text = _clean_text(texto)
    if role == "cliente":
        audiencia = "todos"
    if audiencia not in ("todos", "equipe"):
        raise MensagemInvalida("Audiencia invalida.")

    if responde_a_id is not None:
        parent = db.get(ProducaoMensagemModel, responde_a_id)
        if parent is None or parent.producao_id != production.id or not _message_visible(role, parent):
            raise MensagemNotFound("Mensagem respondida nao encontrada.")

    linked = None
    if arquivo_id is not None:
        linked = db.get(ProducaoArquivoModel, arquivo_id)
        if linked is None or linked.producao_id != production.id or not _file_visible(role, linked):
            raise MensagemNotFound("Arquivo nao encontrado.")
        if audiencia == "todos" and not _file_visible("cliente", linked):
            raise MensagemInvalida(
                "Este arquivo nao esta visivel ao cliente. Libere o arquivo ou envie como mensagem interna."
            )

    model = ProducaoMensagemModel(
        producao_id=production.id,
        autor_usuario_id=user.id,
        autor_papel=role,
        audiencia=audiencia,
        texto=text,
        responde_a_id=responde_a_id,
        arquivo_id=arquivo_id,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    files = {linked.id: linked} if linked is not None else {}
    visible = {responde_a_id} if responde_a_id is not None else set()
    return _serialize(role, user.id, model, files, visible)
