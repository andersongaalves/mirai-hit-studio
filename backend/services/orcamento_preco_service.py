"""AUD6-S03-001: the public budget price is recalculated from the catalog.

The site calculator shows an estimate in the browser, but the value that can
become a proposal price is computed here from the selected service or combo,
the calculator settings and the current discount. A value sent by the browser
is never trusted on its own.
"""
from decimal import ROUND_HALF_UP, Decimal

from models.combo import ComboModel
from models.config import ConfigModel
from models.servico import ServicoModel
from services import promocao_service

CENT = Decimal("0.01")
# Bounds mirror the calculator inputs; anything outside them is not a real selection.
NUMBERS = {
    "duracao": (30, 7200),
    "pessoas": (1, 50),
    "canais_voz": (1, 500),
    "melodias": (1, 500),
    "canais_inst": (1, 500),
}
CHOICES = {
    "inst_aberto": {"sim", "nao"},
    "instrumentacao": {"eletronicos", "hibridos", "gravados"},
    "exclusividade": {"sim", "nao"},
    "revisoes": {"1", "2", "3"},
    "prazo": {"normal", "urgente", "express"},
}


class SelecaoInvalida(ValueError):
    pass


def _number(parametros, name, default):
    raw = parametros.get(name, default)
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        raise SelecaoInvalida(name) from None
    low, high = NUMBERS[name]
    if not low <= value <= high:
        raise SelecaoInvalida(name)
    return value


def _choice(parametros, name, default):
    value = str(parametros.get(name, default)).strip()
    if value not in CHOICES[name]:
        raise SelecaoInvalida(name)
    return value


def _money(value):
    return Decimal(str(value or 0))


def _extras(config, names, parametros):
    total = Decimal(0)
    for name in names:
        if name == "duracao":
            total += max(0, _number(parametros, name, 180) - 180) * _money(config.val_extra_duracao)
        elif name == "pessoas":
            total += max(0, _number(parametros, name, 1) - 1) * _money(config.val_extra_pessoa)
        elif name == "canais_voz":
            total += max(0, _number(parametros, name, 5) - 5) * _money(config.val_extra_canal_voz)
        elif name == "melodias":
            total += max(0, _number(parametros, name, 5) - 5) * _money(config.val_extra_melodia)
        elif name == "revisoes":
            total += max(0, int(_choice(parametros, name, "1")) - 1) * _money(config.val_extra_revisao)
        elif name == "inst_aberto":
            if _choice(parametros, name, "nao") == "sim":
                total += _number(parametros, "canais_inst", 1) * _money(config.val_extra_canal_inst)
        elif name == "instrumentacao":
            kind = _choice(parametros, name, "eletronicos")
            total += {"hibridos": _money(config.val_inst_hibrido),
                      "gravados": _money(config.val_inst_gravado)}.get(kind, Decimal(0))
        elif name == "exclusividade":
            if _choice(parametros, name, "sim") == "nao":
                total -= _money(config.val_lease_desconto)
        elif name == "prazo":
            kind = _choice(parametros, name, "normal")
            total += {"urgente": _money(config.val_prazo_urgente),
                      "express": _money(config.val_prazo_express)}.get(kind, Decimal(0))
    return total


def calcular(db, selecao):
    """Return (catalog name, price) for a public calculator selection."""
    if selecao.combo_id is not None:
        model = db.get(ComboModel, selecao.combo_id)
        if model is None or not model.ativo:
            raise SelecaoInvalida("combo")
        from services import combo_service

        names = combo_service.serializar(model)["parametros"]
        base = _money(model.preco_base)
    else:
        model = db.get(ServicoModel, selecao.servico_id)
        if model is None or (model.categoria or "") == "combo":
            raise SelecaoInvalida("servico")
        names = model.parametros or ""
        base = _money(model.valor_base)
    unknown = set(selecao.parametros) - set(NUMBERS) - set(CHOICES)
    if unknown:
        raise SelecaoInvalida("parametros")
    config = db.query(ConfigModel).order_by(ConfigModel.id).first() or ConfigModel()
    names = [name.strip() for name in dict.fromkeys(names.split(",")) if name.strip()]
    total = base + _extras(config, names, selecao.parametros)
    percentual = promocao_service.preco(model, promocao_service.desconto_global(db))["desconto_percentual"]
    total = total * (Decimal(1) - Decimal(str(percentual)) / 100)
    return model.nome, max(total, Decimal(0)).quantize(CENT, rounding=ROUND_HALF_UP)


def aplicar(db, dados):
    """Return the budget payload with the server price (or no price when unverifiable)."""
    informado = None
    if dados.valor_total is not None:
        informado = Decimal(str(dados.valor_total)).quantize(CENT, rounding=ROUND_HALF_UP)
    nota = None
    if dados.selecao is None:
        nome, preco = dados.servico, None
        if informado is not None:
            nota = (f"Estimativa informada pelo navegador, sem seleção verificável: "
                    f"R$ {informado:.2f}. Defina o preço na proposta.")
    else:
        nome, preco = calcular(db, dados.selecao)
        if informado is not None and abs(informado - preco) > CENT:
            nota = (f"Estimativa exibida no site: R$ {informado:.2f}; "
                    f"preço de catálogo recalculado: R$ {preco:.2f}.")
    detalhes = dados.detalhes or ""
    if nota:
        detalhes = (detalhes[: 20000 - len(nota) - 2] + "\n\n" + nota).strip()
    return dados.model_copy(update={
        "servico": nome[:100],
        "valor_total": float(preco) if preco is not None else None,
        "detalhes": detalhes or None,
    })
