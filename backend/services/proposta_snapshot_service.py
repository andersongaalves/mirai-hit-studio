"""Roadmap 3.0, 5.05: catalog origin and economic snapshot of proposals.

The catalog (services, base price, stage weights) is only a template. When a proposal is
sent, the negotiated line values and the stage weights in force are frozen into
`propostas.snapshot_economico`; later catalog edits never rewrite it. Values are
distributed in cents with a deterministic largest-remainder rule so the stages of a line
always add up exactly to that line's contracted value.
"""
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from models.servico import ServicoModel
from schemas.proposta import PropostaItem, SnapshotEconomico
from services import proposta_service as service
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

CENT = Decimal("0.01")
FULL_WEIGHT = 10000  # 100.00% expressed in hundredths of a percent.


def _cents(value: Decimal) -> int:
    return int((value.quantize(CENT, rounding=ROUND_HALF_UP) * 100).to_integral_value())


def _money(cents: int) -> Decimal:
    return (Decimal(cents) / 100).quantize(CENT)


def _weight(value) -> int:
    return int((Decimal(str(value)).quantize(CENT) * 100).to_integral_value())


def distribuir_centavos(total_centavos: int, pesos: list[int]) -> list[int]:
    """Split `total_centavos` by weights (hundredths of a percent, summing to 10000).

    Each share gets the floor of its exact value; the leftover cents go one by one to
    the largest fractional remainders, ties broken by position. Zero weights always get
    zero and the result always sums to the total.
    """
    if total_centavos < 0 or any(peso < 0 for peso in pesos) or sum(pesos) != FULL_WEIGHT:
        raise ValueError("invalid_distribution")
    exatos = [total_centavos * peso for peso in pesos]
    partes = [valor // FULL_WEIGHT for valor in exatos]
    sobra = total_centavos - sum(partes)
    ordem = sorted(range(len(pesos)), key=lambda index: (-(exatos[index] % FULL_WEIGHT), index))
    for index in ordem[:sobra]:
        partes[index] += 1
    return partes


def carregar_servicos(db: Session, ids) -> dict[int, ServicoModel]:
    ids = sorted({identifier for identifier in ids if identifier is not None})
    if not ids:
        return {}
    query = select(ServicoModel).where(ServicoModel.id.in_(ids)).options(selectinload(ServicoModel.etapas))
    return {servico.id: servico for servico in db.scalars(query)}


def carregar_combos(db: Session, ids) -> dict:
    from services import combo_service  # Local import: combo_service imports schemas only.

    ids = {identifier for identifier in ids if identifier is not None}
    return {combo.id: combo for combo in combo_service.carregar(db, ids)} if ids else {}


def validar_servicos(db: Session, itens: list[PropostaItem]) -> None:
    """Draft rule: every catalog reference must point to an existing service or active combo."""
    ids = {item.servico_id for item in itens if item.servico_id is not None}
    if ids - set(carregar_servicos(db, ids)):
        raise service.PropostaInvalida("Servico do catalogo nao encontrado.")
    combo_ids = {item.combo_id for item in itens if item.combo_id is not None}
    combos = carregar_combos(db, combo_ids)
    if combo_ids - {combo_id for combo_id, combo in combos.items() if combo.ativo}:
        raise service.PropostaInvalida("Combo do catalogo nao encontrado ou inativo.")


def _linha(item: PropostaItem):
    bruto = (item.quantidade * item.valor_unitario).quantize(CENT, rounding=ROUND_HALF_UP)
    desconto = min(bruto, item.desconto.quantize(CENT, rounding=ROUND_HALF_UP))
    return bruto, desconto, bruto - desconto


def _componentes(combo, valor_contratado: Decimal):
    """5.08, first level: split the combo value among its services by catalog price.

    Weights are the services' base prices in cents (equal split if they are all zero), so
    the components always add up exactly to the contracted value of the line.
    """
    itens = sorted(combo.itens, key=lambda item: item.ordem)
    if not itens:
        raise ValueError("combo_vazio")
    precos = [_cents(Decimal(str(item.servico.valor_base or 0))) for item in itens]
    if sum(precos) <= 0:
        precos = [1] * len(itens)
    valores = _distribuir_por_precos(_cents(valor_contratado), precos)
    return [(indice, item.servico, _money(valor)) for indice, (item, valor) in enumerate(zip(itens, valores), start=1)]


def _distribuir_por_precos(total_centavos: int, precos: list[int]) -> list[int]:
    """Largest-remainder split of cents proportional to integer prices (exact sum)."""
    soma = sum(precos)
    exatos = [total_centavos * preco for preco in precos]
    partes = [valor // soma for valor in exatos]
    sobra = total_centavos - sum(partes)
    ordem = sorted(range(len(precos)), key=lambda index: (-(exatos[index] % soma), index))
    for index in ordem[:sobra]:
        partes[index] += 1
    return partes


def _etapas(servico: ServicoModel, valor_contratado: Decimal):
    etapas = sorted(servico.etapas, key=lambda etapa: etapa.ordem)
    if not etapas:
        return []
    pesos = [_weight(etapa.peso_percentual) for etapa in etapas]
    valores = distribuir_centavos(_cents(valor_contratado), pesos)
    return [{
        "ordem": index,
        "nome": etapa.nome,
        "peso_percentual": str(Decimal(str(etapa.peso_percentual)).quantize(CENT)),
        "valor": str(_money(valor)),
        "prazo_dias": etapa.prazo_dias,
        "unidade": etapa.unidade or "",
        "revisoes_incluidas": etapa.revisoes_incluidas,
        "depende_da_anterior": bool(etapa.depende_da_anterior),
        "administrativa": bool(etapa.administrativa),
    } for index, (etapa, valor) in enumerate(zip(etapas, valores), start=1)]


def _linha_combo(indice, item, combo, bruto, desconto, valor, *, estrito: bool) -> dict:
    """5.08: combo line. Value -> components (by catalog price) -> stages (by weight).

    Each stage keeps its service origin, so nothing is counted twice: the sum of the
    components is the contracted value and the stages of a component add up to its share.
    """
    componentes, etapas = [], []
    disponivel = combo is not None and bool(combo.itens)
    if not disponivel and estrito:
        raise service.PropostaConflito(
            f"O combo do item {indice} foi removido do catalogo ou nao tem servicos; revise os itens."
        )
    if disponivel:
        for posicao, servico, alocado in _componentes(combo, valor):
            try:
                etapas_servico = _etapas(servico, alocado)
            except ValueError:
                if estrito:
                    raise service.PropostaConflito(
                        f"As etapas do servico '{servico.nome}' (combo '{combo.nome}') nao somam 100%; revise o catalogo."
                    ) from None
                etapas_servico = []
            componentes.append({
                "indice": posicao,
                "servico_id": servico.id,
                "servico_nome": servico.nome,
                "preco_catalogo": str(_money(_cents(Decimal(str(servico.valor_base or 0))))),
                "valor_alocado": str(alocado),
            })
            for etapa in etapas_servico:
                etapas.append({**etapa, "servico_id": servico.id, "servico_nome": servico.nome,
                               "componente_indice": posicao})
        if sum(Decimal(componente["valor_alocado"]) for componente in componentes) != valor:
            raise service.PropostaConflito("Distribuicao do combo inconsistente; nenhuma alteracao confirmada.")
    return {
        "indice": indice,
        "descricao": item.descricao,
        "servico_id": None,
        "servico_nome": None,
        "preco_catalogo": str(_money(_cents(Decimal(str(combo.preco_base))))) if disponivel else None,
        "catalogo_disponivel": disponivel,
        "quantidade": str(item.quantidade),
        "valor_unitario": str(item.valor_unitario),
        "bruto": str(bruto),
        "desconto": str(desconto),
        "valor_contratado": str(valor),
        "etapas": etapas,
        "combo_id": item.combo_id,
        "combo_nome": combo.nome if combo is not None else None,
        "componentes": componentes,
    }


def _congelar_cotas(db: Session, linhas: list[dict]) -> None:
    """5.09: freeze the file quotas of every contracted catalog service (single or in a combo)."""
    from services import cota_arquivo_service  # Local import keeps the module graph acyclic.

    servicos = [linha["servico_id"] for linha in linhas if linha.get("servico_id") and linha["catalogo_disponivel"]]
    servicos += [componente["servico_id"] for linha in linhas for componente in linha.get("componentes") or []]
    cotas = cota_arquivo_service.carregar_cotas(db, servicos)
    for linha in linhas:
        if linha.get("componentes"):
            for componente in linha["componentes"]:
                componente["cotas_arquivos"] = cotas.get(componente["servico_id"], [])
        elif linha.get("servico_id") and linha["catalogo_disponivel"]:
            linha["cotas_arquivos"] = cotas.get(linha["servico_id"], [])


def _congelar_politicas(db: Session, linhas: list[dict]) -> None:
    """5.10: freeze the resolved portal policies of every contracted catalog service."""
    from services import politica_service  # Local import keeps the module graph acyclic.

    servicos = [linha["servico_id"] for linha in linhas if linha.get("servico_id") and linha["catalogo_disponivel"]]
    servicos += [componente["servico_id"] for linha in linhas for componente in linha.get("componentes") or []]
    politicas = politica_service.resolver_servicos(db, servicos)
    for linha in linhas:
        if linha.get("componentes"):
            for componente in linha["componentes"]:
                componente["politicas"] = politicas.get(componente["servico_id"])
        elif linha.get("servico_id") and linha["catalogo_disponivel"]:
            linha["politicas"] = politicas.get(linha["servico_id"])


def construir(db: Session, model, *, origem: str, estrito: bool) -> dict:
    """Builds the snapshot dict (JSON-ready) for the proposal's current items.

    estrito=True (send): a referenced service that vanished or has invalid weights stops
    the operation. estrito=False (late acceptance of a pre-5.05 proposal): the line is
    kept with `catalogo_disponivel=false` and no stages, so acceptance is never blocked.
    """
    itens = [PropostaItem.model_validate(item) for item in model.itens_json]
    servicos = carregar_servicos(db, [item.servico_id for item in itens])
    combos = carregar_combos(db, [item.combo_id for item in itens])
    linhas = []
    for indice, item in enumerate(itens, start=1):
        bruto, desconto, valor = _linha(item)
        if item.combo_id is not None:
            linhas.append(_linha_combo(indice, item, combos.get(item.combo_id), bruto, desconto, valor,
                                       estrito=estrito))
            continue
        servico = servicos.get(item.servico_id) if item.servico_id is not None else None
        etapas = []
        if servico is not None:
            try:
                etapas = _etapas(servico, valor)
            except ValueError:
                if estrito:
                    raise service.PropostaConflito(
                        f"As etapas do servico '{servico.nome}' nao somam 100%; revise o catalogo."
                    ) from None
                servico = None
        elif item.servico_id is not None and estrito:
            raise service.PropostaConflito(
                f"O servico do item {indice} foi removido do catalogo; revise os itens antes de enviar."
            )
        linhas.append({
            "indice": indice,
            "descricao": item.descricao,
            "servico_id": item.servico_id,
            "servico_nome": servico.nome if servico is not None else None,
            "preco_catalogo": (
                str(Decimal(str(servico.valor_base)).quantize(CENT, rounding=ROUND_HALF_UP))
                if servico is not None else None
            ),
            "catalogo_disponivel": servico is not None,
            "quantidade": str(item.quantidade),
            "valor_unitario": str(item.valor_unitario),
            "bruto": str(bruto),
            "desconto": str(desconto),
            "valor_contratado": str(valor),
            "etapas": etapas,
        })
    _congelar_cotas(db, linhas)
    _congelar_politicas(db, linhas)
    totais = service.calcular_totais(itens)
    if sum(Decimal(linha["valor_contratado"]) for linha in linhas) != totais.total:
        raise service.PropostaConflito("Snapshot economico inconsistente; nenhuma alteracao confirmada.")
    snapshot = {
        "versao_snapshot": 1,
        "proposta_versao": model.versao,
        "moeda": "BRL",
        "origem": origem,
        "congelado_em": datetime.now(timezone.utc).isoformat(),
        "subtotal": str(totais.subtotal),
        "desconto": str(totais.desconto),
        "total": str(totais.total),
        "itens": linhas,
    }
    return SnapshotEconomico.model_validate(snapshot).model_dump(mode="json")


def congelar(db: Session, model, *, origem: str, estrito: bool) -> bool:
    """Freezes the snapshot once. Returns False when it already existed (never rewritten)."""
    if model.snapshot_economico:
        return False
    snapshot = construir(db, model, origem=origem, estrito=estrito)
    model.snapshot_economico = snapshot
    model.snapshot_congelado_em = datetime.fromisoformat(snapshot["congelado_em"])
    db.flush()
    return True
