import re

from sqlalchemy.orm import Session

from crud import crud_cliente
from models.producao import ProducaoModel
from schemas.cliente import (
    ClienteCreate,
    ClienteDetail,
    ClienteHistoricoItem,
    ClienteResponse,
    ClienteSummary,
    ClienteUpdate,
)


class ClienteNaoEncontrado(Exception):
    pass


class ClienteConflito(Exception):
    pass


class ClienteInvalido(Exception):
    pass


def normalizar_email(email: str | None) -> str | None:
    return email.strip().lower() if email else None


def normalizar_telefone(telefone: str | None) -> str | None:
    if not telefone:
        return None
    digitos = re.sub(r"\D", "", telefone)
    return digitos or None


def _normalizar(dados: dict) -> dict:
    normalizados = dict(dados)
    if "email" in normalizados:
        normalizados["email"] = normalizar_email(normalizados["email"])
    if "telefone" in normalizados:
        normalizados["telefone"] = normalizar_telefone(normalizados["telefone"])
    return normalizados


def _candidatos(db: Session, email: str | None, telefone: str | None):
    por_email = crud_cliente.buscar_por_email(db, email)
    por_telefone = crud_cliente.buscar_por_telefone(db, telefone)
    if por_email and por_telefone and por_email.id != por_telefone.id:
        return None, True
    return por_email or por_telefone, False


def resolver_para_orcamento(
    db: Session,
    *,
    nome: str,
    email: str | None,
    telefone: str | None,
    erro_em_conflito: bool = False,
):
    email = normalizar_email(email)
    telefone = normalizar_telefone(telefone)
    cliente, conflito = _candidatos(db, email, telefone)
    if conflito:
        if erro_em_conflito:
            raise ClienteConflito("Identificadores pertencem a clientes diferentes.")
        return None
    if cliente:
        complementos = {}
        if not cliente.email and email:
            complementos["email"] = email
        if not cliente.telefone and telefone:
            complementos["telefone"] = telefone
        if complementos:
            crud_cliente.atualizar_sem_commit(db, cliente, complementos)
        return cliente
    return crud_cliente.criar_sem_commit(db, {
        "nome": nome.strip(),
        "email": email,
        "telefone": telefone,
        "observacoes": "",
        "ativo": True,
    })


def criar(db: Session, dados: ClienteCreate):
    payload = _normalizar(dados.model_dump())
    if not payload.get("email") and not payload.get("telefone"):
        raise ClienteInvalido("Informe email ou telefone.")
    existente, conflito = _candidatos(db, payload.get("email"), payload.get("telefone"))
    if conflito or existente:
        raise ClienteConflito("Cliente com este email ou telefone ja existe.")
    try:
        cliente = crud_cliente.criar_sem_commit(db, payload)
        resposta = ClienteResponse.model_validate(cliente)
        db.commit()
        return resposta
    except Exception:
        db.rollback()
        raise


def atualizar(db: Session, cliente_id: int, dados: ClienteUpdate):
    cliente = crud_cliente.buscar_por_id(db, cliente_id)
    if not cliente:
        raise ClienteNaoEncontrado("Cliente nao encontrado.")
    payload = _normalizar(dados.model_dump(exclude_unset=True))
    contato_email = payload.get("email", cliente.email)
    contato_telefone = payload.get("telefone", cliente.telefone)
    if not contato_email and not contato_telefone:
        raise ClienteInvalido("Informe email ou telefone.")
    por_email, conflito_email = _candidatos(db, contato_email, None)
    por_telefone, conflito_telefone = _candidatos(db, None, contato_telefone)
    outros = {item.id for item in (por_email, por_telefone) if item and item.id != cliente.id}
    if conflito_email or conflito_telefone or outros:
        raise ClienteConflito("Email ou telefone pertence a outro cliente.")
    try:
        crud_cliente.atualizar_sem_commit(db, cliente, payload)
        resposta = ClienteResponse.model_validate(cliente)
        db.commit()
        return resposta
    except Exception:
        db.rollback()
        raise


def listar(db: Session, busca: str = "", ativo: bool | None = None):
    return [
        ClienteSummary.model_validate({
            **ClienteResponse.model_validate(cliente).model_dump(),
            "total_orcamentos": total,
            "ultima_interacao": ultima,
        })
        for cliente, total, ultima in crud_cliente.listar(db, busca, ativo)
    ]


def buscar(db: Session, cliente_id: int):
    cliente = crud_cliente.buscar_por_id(db, cliente_id, com_orcamentos=True)
    if not cliente:
        raise ClienteNaoEncontrado("Cliente nao encontrado.")

    ids = [orcamento.id for orcamento in cliente.orcamentos]
    producoes = (
        db.query(ProducaoModel)
        .filter(ProducaoModel.orcamento_id.in_(ids))
        .all()
        if ids else []
    )
    historico = []
    for orcamento in cliente.orcamentos:
        if orcamento.data_solicitacao:
            historico.append(ClienteHistoricoItem(
                evento="orcamento_criado",
                titulo=f"Orcamento criado: {orcamento.servico}",
                data=orcamento.data_solicitacao,
                orcamento_id=orcamento.id,
            ))
        proposta = orcamento.proposta
        if proposta and proposta.created_at:
            historico.append(ClienteHistoricoItem(
                evento="proposta_criada",
                titulo=f"Proposta criada: {proposta.numero}",
                data=proposta.created_at,
                orcamento_id=orcamento.id,
                proposta_id=proposta.id,
            ))
        if proposta and proposta.enviada_em:
            historico.append(ClienteHistoricoItem(
                evento="proposta_enviada",
                titulo=f"Proposta enviada: {proposta.numero}",
                data=proposta.enviada_em,
                orcamento_id=orcamento.id,
                proposta_id=proposta.id,
            ))
        if proposta and proposta.aprovada_em:
            historico.append(ClienteHistoricoItem(
                evento="proposta_aprovada",
                titulo=f"Proposta aprovada: {proposta.numero}",
                data=proposta.aprovada_em,
                orcamento_id=orcamento.id,
                proposta_id=proposta.id,
            ))
    for producao in producoes:
        if producao.created_at:
            historico.append(ClienteHistoricoItem(
                evento="producao_criada",
                titulo=f"Producao criada: {producao.servico}",
                data=producao.created_at,
                orcamento_id=producao.orcamento_id,
                producao_id=producao.id,
            ))
    historico.sort(key=lambda item: item.data, reverse=True)
    return ClienteDetail.model_validate({
        **ClienteResponse.model_validate(cliente).model_dump(),
        "total_orcamentos": len(cliente.orcamentos),
        "historico": historico,
    })
