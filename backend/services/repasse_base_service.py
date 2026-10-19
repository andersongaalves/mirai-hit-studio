"""Exact 80/20 economic pools; never a transfer or a second revenue event."""
from services.proposta_snapshot_service import (
    _distribuir_por_precos,
    distribuir_centavos,
)


def distribuir_pool(total, bases):
    if type(total) is not int or total < 0 or any(type(value) is not int or value < 0 for value in bases):
        raise ValueError("invalid_payout_pool")
    if total > sum(bases):
        raise ValueError("payout_pool_exceeds_gross")
    if not sum(bases):
        return [0] * len(bases)
    return _distribuir_por_precos(total, bases)


def parcelas_produtor(bases):
    """Freeze the producer pool once for the entire economic origin, then divide it."""
    if any(type(value) is not int or value < 0 for value in bases):
        raise ValueError("invalid_payout_basis")
    total = sum(bases)
    return distribuir_pool(distribuir_centavos(total, [8000, 2000])[0], bases)


def reservar_parcela(*, bruto_restante, produtor_restante, unidades_restantes, unidades):
    values = (bruto_restante, produtor_restante, unidades_restantes, unidades)
    if (any(type(value) is not int or value < 0 for value in values)
            or produtor_restante > bruto_restante or not 0 < unidades <= unidades_restantes):
        raise ValueError("invalid_credit_payout_balance")
    return (bruto_restante * unidades // unidades_restantes,
            produtor_restante * unidades // unidades_restantes)
