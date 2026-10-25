"""AUD6-S09-006: one search box in the Admin, results grouped by kind.

Read-only and Admin-only. Test chains stay out, matching the sections' default
"real" view, so a result always shows up when its section opens.
"""
import re

from models import (
    BeatModel,
    ClienteModel,
    OrcamentoModel,
    ProducaoModel,
    PropostaModel,
    UsuarioModel,
)
from sqlalchemy import String, cast, or_, select

LIMITE = 5


def _padrao(termo):
    escaped = re.sub(r"([\\%_])", r"\\\1", termo)
    return f"%{escaped}%"


def _like(coluna, padrao):
    return coluna.ilike(padrao, escape="\\")


def buscar(db, termo):
    termo = " ".join(termo.split())
    padrao = _padrao(termo)
    numero = int(termo.lstrip("#")) if termo.lstrip("#").isdigit() else None
    teste = select(OrcamentoModel.id).where(OrcamentoModel.is_test.is_(True))
    grupos = []

    clientes = db.scalars(
        select(ClienteModel)
        .where(ClienteModel.is_test.is_(False), or_(_like(ClienteModel.nome, padrao), _like(ClienteModel.email, padrao)))
        .order_by(ClienteModel.nome).limit(LIMITE)
    ).all()
    grupos.append(("clientes", "Clientes", "section-clientes", [
        {"id": c.id, "titulo": c.nome, "detalhe": c.email or "", "filtro": c.nome} for c in clientes
    ]))

    filtros = [_like(OrcamentoModel.nome_cliente, padrao), _like(OrcamentoModel.email, padrao),
               _like(OrcamentoModel.servico, padrao)]
    if numero is not None:
        filtros.append(OrcamentoModel.id == numero)
    orcamentos = db.scalars(
        select(OrcamentoModel).where(OrcamentoModel.is_test.is_(False), or_(*filtros))
        .order_by(OrcamentoModel.id.desc()).limit(LIMITE)
    ).all()
    grupos.append(("orcamentos", "Orçamentos", "section-orcamentos", [
        {"id": o.id, "titulo": f"Orçamento #{o.id} · {o.nome_cliente}", "detalhe": o.servico, "filtro": o.nome_cliente}
        for o in orcamentos
    ]))

    propostas = db.execute(
        select(PropostaModel.id, PropostaModel.numero, OrcamentoModel.nome_cliente)
        .join(OrcamentoModel, OrcamentoModel.id == PropostaModel.orcamento_id)
        .where(OrcamentoModel.is_test.is_(False), _like(cast(PropostaModel.numero, String), padrao))
        .order_by(PropostaModel.id.desc()).limit(LIMITE)
    ).all()
    grupos.append(("propostas", "Propostas", "section-orcamentos", [
        {"id": pid, "titulo": f"Proposta {numero_proposta}", "detalhe": nome, "filtro": nome}
        for pid, numero_proposta, nome in propostas
    ]))

    filtros = [_like(ProducaoModel.titulo, padrao), _like(ProducaoModel.servico, padrao)]
    if numero is not None:
        filtros.append(ProducaoModel.id == numero)
    producoes = db.scalars(
        select(ProducaoModel)
        .where(or_(ProducaoModel.orcamento_id.is_(None), ~ProducaoModel.orcamento_id.in_(teste)), or_(*filtros))
        .order_by(ProducaoModel.id.desc()).limit(LIMITE)
    ).all()
    grupos.append(("producoes", "Produções", "section-producoes", [
        {"id": p.id, "titulo": p.titulo, "detalhe": p.servico, "filtro": p.titulo} for p in producoes
    ]))

    beats = db.scalars(
        select(BeatModel).where(_like(BeatModel.titulo, padrao)).order_by(BeatModel.id.desc()).limit(LIMITE)
    ).all()
    grupos.append(("beats", "Beats", "section-beats", [
        {"id": b.id, "titulo": b.titulo, "detalhe": b.status, "filtro": None} for b in beats
    ]))

    usuarios = db.scalars(
        select(UsuarioModel)
        .where(UsuarioModel.is_test.is_(False),
               or_(_like(UsuarioModel.username, padrao), _like(UsuarioModel.nome_exibicao, padrao)))
        .order_by(UsuarioModel.username).limit(LIMITE)
    ).all()
    grupos.append(("usuarios", "Usuários", "section-usuarios", [
        {"id": u.id, "titulo": u.nome_exibicao or u.username, "detalhe": f"{u.username} · {u.role}", "filtro": u.username}
        for u in usuarios
    ]))

    return {
        "termo": termo,
        "grupos": [
            {"tipo": tipo, "rotulo": rotulo, "secao": secao, "itens": itens}
            for tipo, rotulo, secao, itens in grupos if itens
        ],
    }
