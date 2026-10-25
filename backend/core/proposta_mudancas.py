"""AUD6-S05-002: what changed between the version the client last saw and the current one.

Pure functions over plain dicts (stdlib only). The previous sent version is kept
in ``propostas.envio_anterior`` when an expired proposal goes back to draft.
"""
from decimal import Decimal, InvalidOperation

CAMPOS_TEXTO = ("objeto", "descricao", "condicoes", "politica_pagamento")


def _numero(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(0)


def _texto(value):
    return " ".join(str(value or "").split())


def _chave(item):
    for origem in ("servico_id", "combo_id", "beat_id"):
        if item.get(origem) is not None:
            return f"{origem}:{item[origem]}:{item.get('licenca_beat') or ''}"
    return "texto:" + _texto(item.get("descricao")).lower()


def _linha(item):
    return {
        "quantidade": str(_numero(item.get("quantidade"))),
        "valor_unitario": str(_numero(item.get("valor_unitario"))),
        "desconto": str(_numero(item.get("desconto"))),
    }


def foto(proposta_dict):
    """The fields worth comparing, taken when a sent proposal returns to draft."""
    return {
        "versao": proposta_dict.get("versao"),
        "enviada_em": proposta_dict.get("enviada_em"),
        "itens": [dict(item) for item in proposta_dict.get("itens") or []],
        "total": str(_numero((proposta_dict.get("totais") or {}).get("total"))),
        **{campo: proposta_dict.get(campo) for campo in CAMPOS_TEXTO},
    }


def comparar(anterior, atual):
    """Returns None when nothing changed (or there is no previous sent version)."""
    if not anterior:
        return None
    antes = {}
    for item in anterior.get("itens") or []:
        antes.setdefault(_chave(item), item)
    depois = {}
    for item in atual.get("itens") or []:
        depois.setdefault(_chave(item), item)
    itens = []
    for chave, item in depois.items():
        velho = antes.get(chave)
        if velho is None:
            itens.append({"tipo": "adicionado", "descricao": _texto(item.get("descricao")), "depois": _linha(item)})
        elif _linha(velho) != _linha(item):
            itens.append({"tipo": "alterado", "descricao": _texto(item.get("descricao")),
                          "antes": _linha(velho), "depois": _linha(item)})
    for chave, item in antes.items():
        if chave not in depois:
            itens.append({"tipo": "removido", "descricao": _texto(item.get("descricao")), "antes": _linha(item)})
    total_antes = _numero(anterior.get("total"))
    total_depois = _numero((atual.get("totais") or {}).get("total"))
    textos = [campo for campo in CAMPOS_TEXTO if _texto(anterior.get(campo)) != _texto(atual.get(campo))]
    if not itens and total_antes == total_depois and not textos:
        return None
    return {
        "versao_anterior": anterior.get("versao"),
        "enviada_em_anterior": anterior.get("enviada_em"),
        "itens": itens,
        "total": {"antes": str(total_antes), "depois": str(total_depois)},
        "campos_alterados": textos,
    }
