"""Service rights. Target budget -> source charge -> lot -> production locks."""
import hashlib
import json
from copy import deepcopy
from decimal import Decimal

from models import (
    ClienteModel,
    CreditoAlocacaoModel,
    CreditoLoteModel,
    CreditoMovimentoModel,
    OrcamentoModel,
    ProducaoArquivoModel,
    ProducaoModel,
    PropostaModel,
    RepasseProdutorModel,
    UsuarioModel,
)
from services import audit_service, financial_service, producao_liberacao_service
from services import carteira_creditos_service as wallet
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError


class AlocacaoInvalida(Exception):
    pass


class AlocacaoNaoEncontrada(Exception):
    pass


class AlocacaoConflito(Exception):
    pass


def _estado(db, alocacao):
    tipos = list(db.scalars(select(CreditoMovimentoModel.tipo).where(
        CreditoMovimentoModel.alocacao_id == alocacao.id).order_by(CreditoMovimentoModel.id)))
    estados = {
        ("reserva",): "reservada", ("reserva", "consumo"): "consumida",
        ("reserva", "devolucao"): "devolvida", ("reserva", "consumo", "estorno"): "estornada",
    }
    if tuple(tipos) not in estados:
        raise AlocacaoConflito("Historico de alocacao requer conciliacao.")
    return estados[tuple(tipos)]


def uso_lote(db, lote_id):
    resultado = {"reservado": Decimal(0), "consumido": Decimal(0), "valor_usado": 0}
    for item in db.scalars(select(CreditoAlocacaoModel).where(CreditoAlocacaoModel.lote_id == lote_id)):
        estado = _estado(db, item)
        if estado in ("reservada", "consumida"):
            resultado["reservado" if estado == "reservada" else "consumido"] += item.quantidade
            resultado["valor_usado"] += item.valor_centavos
    return resultado


def _response(db, item):
    lote = db.get(CreditoLoteModel, item.lote_id)
    return {"id": item.id, "producao_id": item.producao_id, "lote_id": lote.id, "servico_nome": lote.servico_nome,
            "unidade": lote.unidade, "quantidade": item.quantidade, "estado": _estado(db, item),
            "created_at": item.created_at, "valor_centavos": item.valor_centavos}


def listar(db, producao_id):
    if db.get(ProducaoModel, producao_id) is None:
        raise AlocacaoNaoEncontrada("Producao nao encontrada.")
    return [_response(db, item) for item in db.scalars(select(CreditoAlocacaoModel).where(
        CreditoAlocacaoModel.producao_id == producao_id).order_by(CreditoAlocacaoModel.id))]


def contexto(db, producao_id):
    from services import credito_producao_service

    production = db.get(ProducaoModel, producao_id)
    if production is None:
        raise AlocacaoNaoEncontrada("Producao nao encontrada.")
    budget = db.get(OrcamentoModel, production.orcamento_id) if production.orcamento_id else None
    client = db.get(ClienteModel, budget.cliente_id) if budget and budget.cliente_id else None
    proposal = (db.scalar(select(PropostaModel.id).where(PropostaModel.orcamento_id == budget.id)) if budget else None)
    mensagem = None
    if not client or not client.ativo:
        mensagem = "Vincule a producao a um orcamento de cliente ativo."
    elif proposal is not None:
        mensagem = "Producao vinculada a contrato comercial; preserve sua origem de pagamento."
    elif not producao_liberacao_service.pipeline_v2_habilitada():
        mensagem = "Movimentacao de creditos indisponivel sem a pipeline V2."
    elif production.status != "aguardando_inicio":
        mensagem = "Novas reservas ficam disponiveis antes do inicio da producao."
    elif (db.scalar(select(ProducaoArquivoModel.id).where(ProducaoArquivoModel.producao_id == production.id)) is not None
          or credito_producao_service.tem_trabalho_previo(db, production)
          or db.scalar(select(RepasseProdutorModel.id).where(RepasseProdutorModel.producao_id == production.id)) is not None):
        mensagem = "Producao com trabalho ou repasse existente requer conciliacao antes de novas reservas."
    options = []
    if mensagem is None:
        from models import CobrancaModel

        for lote in db.scalars(select(CreditoLoteModel).where(CreditoLoteModel.cliente_id == client.id).order_by(CreditoLoteModel.id)):
            charge = db.get(CobrancaModel, lote.cobranca_id)
            if charge is None or charge.cliente_id != client.id or not wallet.financiamento_valido(charge):
                continue
            uso = uso_lote(db, lote.id)
            remaining = lote.quantidade - uso["reservado"] - uso["consumido"]
            if remaining > 0 and lote.contrato_sha256 == wallet._fingerprint(charge.proposta):
                options.append({"id": lote.id, "servico_nome": lote.servico_nome, "unidade": lote.unidade,
                                "disponivel": str(remaining)})
    return {"producao_status": production.status, "pode_reservar": mensagem is None,
            "mensagem": mensagem, "lotes": options, "alocacoes": listar(db, producao_id)}


def _fingerprint(tipo, producao_id, autor_id, payload, *, alocacao_id=None, cliente_id=None):
    data = {"tipo": tipo, "producao_id": producao_id, "autor_id": autor_id,
            "alocacao_id": alocacao_id, "cliente_id": cliente_id,
            "payload": payload.model_dump(mode="json", exclude={"idempotency_key"})}
    if "quantidade" in data["payload"]:
        data["payload"]["quantidade"] = format(payload.quantidade.normalize(), "f")
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _replay(db, model, key, digest):
    previous = db.scalar(select(model).where(model.idempotency_key == key))
    if previous is not None and previous.request_sha256 != digest:
        raise AlocacaoConflito("Chave de repeticao ja utilizada por outra operacao.")
    return previous


def _bloquear(db, lote_id, producao_id):
    target = db.get(ProducaoModel, producao_id)
    if target is None or target.orcamento_id is None:
        raise AlocacaoNaoEncontrada("Producao sem orcamento vinculado a cliente.")
    budget_id = target.orcamento_id
    budget = db.scalar(select(OrcamentoModel).where(OrcamentoModel.id == budget_id).with_for_update()
                      .execution_options(populate_existing=True))
    found = db.get(CreditoLoteModel, lote_id)
    if found is None:
        raise AlocacaoNaoEncontrada("Lote nao encontrado.")
    charge = financial_service.bloquear_cobranca(db, found.cobranca_id)
    lote = db.scalar(select(CreditoLoteModel).where(CreditoLoteModel.id == lote_id).with_for_update()
                     .execution_options(populate_existing=True))
    production = db.scalar(select(ProducaoModel).where(ProducaoModel.id == producao_id).with_for_update()
                           .execution_options(populate_existing=True))
    if production is None:
        raise AlocacaoNaoEncontrada("Producao nao encontrada.")
    client = db.get(ClienteModel, lote.cliente_id)
    if (charge is None or lote.cobranca_id != charge.id or charge.cliente_id != lote.cliente_id
            or budget is None or production.orcamento_id != budget_id
            or budget.cliente_id != lote.cliente_id or not client or not client.ativo):
        raise AlocacaoConflito("Titularidade da producao ou dos creditos requer conciliacao.")
    if db.scalar(select(PropostaModel.id).where(PropostaModel.orcamento_id == budget.id)) is not None:
        raise AlocacaoConflito("Producao com proposta comercial nao pode receber outra origem de pagamento.")
    if db.scalar(select(RepasseProdutorModel.id).where(RepasseProdutorModel.producao_id == production.id)) is not None:
        raise AlocacaoConflito("Producao com repasse legado requer conciliacao antes de usar creditos.")
    if db.scalar(select(CreditoAlocacaoModel.id).where(CreditoAlocacaoModel.producao_id == production.id,
                CreditoAlocacaoModel.cliente_id != lote.cliente_id)) is not None:
        raise AlocacaoConflito("Producao possui direitos de outro titular.")
    return lote, charge, production


def _validar_financiamento(db, lote, charge):
    if not wallet.financiamento_valido(charge):
        raise AlocacaoConflito("Creditos bloqueados por pendencia financeira ou conciliacao.")
    try:
        wallet.creditar_cobranca_bloqueada(db, charge)
    except (financial_service.FinanceiroConflito, financial_service.FinanceiroInvalido) as error:
        raise AlocacaoConflito(str(error)) from None
    if lote.contrato_sha256 != wallet._fingerprint(charge.proposta):
        raise AlocacaoConflito("Origem contratual dos creditos requer conciliacao.")


def _snapshot(lote, proposta):
    linha = next(i for i in proposta.snapshot_economico["itens"] if i["indice"] == lote.linha)
    parte = (next(i for i in linha["componentes"] if i["indice"] == lote.componente)
             if linha.get("componentes") else linha)
    # Preserve the negotiated rules, not today's catalog, for subsequent production stages.
    return deepcopy({"servico_id": lote.servico_id, "servico_nome": lote.servico_nome,
                     "contrato_sha256": lote.contrato_sha256, "proposta_id": proposta.id,
                     "linha": lote.linha, "componente": lote.componente, "unidade": lote.unidade,
                     "quantidade_creditos_lote": str(lote.quantidade), "quantidade_planos_lote": linha["quantidade"],
                     "etapas": [e for e in linha.get("etapas", [])
                                if not linha.get("componentes") or e.get("componente_indice") == lote.componente],
                     "politicas": parte.get("politicas"),
                     "cotas_arquivos": parte.get("cotas_arquivos", [])})


def _parcela_produtor(db, lote, proposta):
    from services.repasse_base_service import parcelas_produtor

    rights = wallet._contrato(proposta).itens
    pools = parcelas_produtor([item.valor_centavos for item in rights])
    source = next((pool for item, pool in zip(rights, pools)
                   if (item.linha, item.componente) == (lote.linha, lote.componente)), None)
    if source is None:
        raise AlocacaoConflito("Base do repasse sem origem contratual.")
    used = 0
    for item in db.scalars(select(CreditoAlocacaoModel).where(CreditoAlocacaoModel.lote_id == lote.id)):
        if _estado(db, item) not in ("reservada", "consumida"):
            continue
        if item.produtor_centavos is None:
            raise AlocacaoConflito("Reserva historica sem base de repasse exige conciliacao.")
        used += item.produtor_centavos
    if used > source:
        raise AlocacaoConflito("Saldo do repasse dos creditos requer conciliacao.")
    return source - used


def _autor(actor):
    if not actor or not actor.ativo or not (actor.is_admin or actor.role == "admin"):
        raise AlocacaoConflito("Somente um administrador ativo pode movimentar creditos.")
    if not producao_liberacao_service.pipeline_v2_habilitada():
        raise AlocacaoConflito("Movimentacao de creditos indisponivel sem a pipeline V2.")


def _movimento(db, item, tipo, actor, motivo, key, digest, request_id):
    movement = CreditoMovimentoModel(alocacao_id=item.id, tipo=tipo, autor_id=actor.id, motivo=motivo,
                                    idempotency_key=key, request_sha256=digest)
    db.add(movement)
    audit_service.record(db, actor=actor, action=f"credits.{tipo}", entity_type="credit_allocation", entity_id=item.id,
                         metadata={"production_id": item.producao_id, "lot_id": item.lote_id,
                                   "quantity": str(item.quantidade), "reason": motivo}, request_id=request_id)
    db.flush()


def reservar(db, producao_id, dados, *, actor, request_id=None, _request_digest=None):
    try:
        from services import credito_producao_service

        _autor(actor)
        key = str(dados.idempotency_key)
        digest = _request_digest or _fingerprint("reserva", producao_id, actor.id, dados)
        lote, charge, production = _bloquear(db, dados.lote_id, producao_id)
        previous = _replay(db, CreditoAlocacaoModel, key, digest)
        if previous is not None:
            result = _response(db, previous)
            db.commit()
            return result
        _validar_financiamento(db, lote, charge)
        if production.status != "aguardando_inicio":
            raise AlocacaoConflito("Reserve creditos antes de iniciar a producao.")
        if (db.scalar(select(ProducaoArquivoModel.id).where(ProducaoArquivoModel.producao_id == production.id)) is not None
                or credito_producao_service.tem_trabalho_previo(db, production)):
            raise AlocacaoConflito("Producao com trabalho existente requer conciliacao; nao substitua sua origem financeira.")
        uso = uso_lote(db, lote.id)
        restante = lote.quantidade - uso["reservado"] - uso["consumido"]
        valor = lote.valor_centavos - uso["valor_usado"]
        if restante < 0 or valor < 0:
            raise AlocacaoConflito("Saldo de creditos requer conciliacao.")
        if dados.quantidade > restante:
            raise AlocacaoConflito("Creditos disponiveis insuficientes.")
        if lote.unidade != "hora" and dados.quantidade != dados.quantidade.to_integral_value():
            raise AlocacaoInvalida("Faixas e canais exigem unidades inteiras.")
        ticks, saldo_ticks = int(dados.quantidade * 1000), int(restante * 1000)
        # Last units carry the remaining cents, so repeated small reservations cannot mint value.
        from services.repasse_base_service import reservar_parcela

        cents, producer_cents = reservar_parcela(bruto_restante=valor,
            produtor_restante=_parcela_produtor(db, lote, charge.proposta),
            unidades_restantes=saldo_ticks, unidades=ticks)
        item = CreditoAlocacaoModel(lote_id=lote.id, producao_id=production.id, cliente_id=lote.cliente_id,
            quantidade=dados.quantidade, valor_centavos=cents, produtor_centavos=producer_cents,
            snapshot_servico=_snapshot(lote, charge.proposta),
            autor_id=actor.id, motivo=dados.motivo, idempotency_key=key, request_sha256=digest)
        db.add(item)
        db.flush()
        _movimento(db, item, "reserva", actor, dados.motivo, key, digest, request_id)
        credito_producao_service.sincronizar(db, production, item)
        result = _response(db, item)
        db.commit()
        return result
    except IntegrityError:
        db.rollback()
        raise AlocacaoConflito("Conflito de repeticao; nenhuma nova reserva confirmada.") from None
    except Exception:
        db.rollback()
        raise


def criar_producao(db, cliente_id, dados, *, actor, request_id=None):
    """Atomic operational budget + production + reservation; no proposal or new receivable."""
    try:
        _autor(actor)
        from schemas.credito_alocacao import ReservaCreditos

        source = db.get(CreditoLoteModel, dados.lote_id)
        if source is None:
            raise AlocacaoNaoEncontrada("Lote nao encontrado.")
        charge = financial_service.bloquear_cobranca(db, source.cobranca_id)
        lote = db.scalar(select(CreditoLoteModel).where(CreditoLoteModel.id == source.id).with_for_update()
                         .execution_options(populate_existing=True))
        client = db.get(ClienteModel, cliente_id)
        producer = db.get(UsuarioModel, dados.produtor_id)
        if not client or not client.ativo or lote.cliente_id != cliente_id:
            raise AlocacaoConflito("Creditos indisponiveis para este cliente.")
        digest = _fingerprint("nova_producao", None, actor.id, dados, cliente_id=cliente_id)
        previous = _replay(db, CreditoAlocacaoModel, str(dados.idempotency_key), digest)
        if previous is not None:
            result = _response(db, previous)
            db.commit()
            return result
        if not producer or not producer.ativo or producer.role != "produtor":
            raise AlocacaoInvalida("Selecione um produtor ativo.")
        _validar_financiamento(db, lote, charge)
        budget = OrcamentoModel(nome_cliente=client.nome, email=client.email or "", whatsapp=client.telefone,
            servico=lote.servico_nome, cliente_id=client.id, produtor_id=producer.id, status="aprovado",
            detalhes=dados.titulo, observacoes="Producao financiada por creditos de servicos.",
            is_test=bool(client.is_test or charge.proposta.orcamento.is_test))
        db.add(budget)
        db.flush()
        production = ProducaoModel(titulo=dados.titulo, cliente=client.nome, servico=lote.servico_nome,
                                   orcamento_id=budget.id, produtor_id=producer.id, status="aguardando_inicio")
        db.add(production)
        db.flush()
        audit_service.record(db, actor=actor, action="production.created_from_credits", entity_type="production",
                             entity_id=production.id, metadata={"lot_id": lote.id, "reason": dados.motivo},
                             request_id=request_id)
        return reservar(db, production.id, ReservaCreditos.model_validate(dados.model_dump(
            exclude={"titulo", "produtor_id"})), actor=actor, request_id=request_id, _request_digest=digest)
    except IntegrityError:
        db.rollback()
        raise AlocacaoConflito("Conflito de repeticao; nenhuma nova producao confirmada.") from None
    except Exception:
        db.rollback()
        raise


def movimentar(db, producao_id, alocacao_id, dados, *, actor, request_id=None):
    try:
        from services import credito_producao_service

        _autor(actor)
        item = db.get(CreditoAlocacaoModel, alocacao_id)
        if item is None or item.producao_id != producao_id:
            raise AlocacaoNaoEncontrada("Alocacao nao encontrada.")
        lote, charge, production = _bloquear(db, item.lote_id, producao_id)
        key = str(dados.idempotency_key)
        digest = _fingerprint(dados.tipo, producao_id, actor.id, dados, alocacao_id=alocacao_id)
        previous = _replay(db, CreditoMovimentoModel, key, digest)
        if previous is not None:
            result = _response(db, item)
            db.commit()
            return result
        estado = _estado(db, item)
        if dados.tipo == "consumo":
            _validar_financiamento(db, lote, charge)
            if item.produtor_centavos is None:
                raise AlocacaoConflito("Reserva historica sem base de repasse exige conciliacao antes do consumo.")
            if estado != "reservada" or production.status not in ("em_producao", "revisao"):
                raise AlocacaoConflito("Consumo exige reserva ativa e producao em andamento.")
        else:
            expected = "reservada" if dados.tipo == "devolucao" else "consumida"
            if estado != expected or production.status != "aguardando_inicio":
                raise AlocacaoConflito("Devolucao ou estorno exige estado compativel e producao sem execucao.")
            if (db.scalar(select(ProducaoArquivoModel.id).where(ProducaoArquivoModel.producao_id == production.id)) is not None
                    or credito_producao_service.tem_trabalho_previo(db, production)):
                raise AlocacaoConflito("Trabalho executado exige conciliacao; nenhum credito foi devolvido.")
        _movimento(db, item, dados.tipo, actor, dados.motivo, key, digest, request_id)
        credito_producao_service.sincronizar(db, production, item)
        result = _response(db, item)
        db.commit()
        return result
    except IntegrityError:
        db.rollback()
        raise AlocacaoConflito("Conflito de repeticao; nenhuma nova movimentacao confirmada.") from None
    except Exception:
        db.rollback()
        raise


def entrega_bloqueada(db, production):
    """None means a historical/non-credit production; never fall back after credit history exists."""
    items = db.scalars(select(CreditoAlocacaoModel).where(CreditoAlocacaoModel.producao_id == production.id)).all()
    if not items:
        return None
    budget = db.get(OrcamentoModel, production.orcamento_id) if production.orcamento_id else None
    active = []
    for item in items:
        estado = _estado(db, item)
        if estado in ("devolvida", "estornada"):
            continue
        active.append(item)
        lote = db.get(CreditoLoteModel, item.lote_id)
        from models import CobrancaModel

        charge = db.get(CobrancaModel, lote.cobranca_id)
        if (estado != "consumida" or not budget or budget.cliente_id != item.cliente_id
                or charge is None or charge.cliente_id != item.cliente_id or not wallet.financiamento_valido(charge)
                or lote.contrato_sha256 != wallet._fingerprint(charge.proposta)):
            return True
    return not active
