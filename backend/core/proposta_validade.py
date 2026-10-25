"""AUD6-S05-001: a sent proposal is valid for 10 calendar days, as the PDF states."""
from datetime import datetime, time, timedelta, timezone

VALIDADE_DIAS = 10
# Brasília time has had no daylight saving since 2019; a fixed offset avoids depending on tzdata.
FUSO = timezone(timedelta(hours=-3), "BRT")


def _aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def valida_ate(enviada_em):
    """End of the 10th calendar day after sending, in the studio's time zone."""
    if enviada_em is None:
        return None
    local = _aware(enviada_em).astimezone(FUSO)
    ultimo_dia = local.date() + timedelta(days=VALIDADE_DIAS)
    return datetime.combine(ultimo_dia, time(23, 59, 59), tzinfo=FUSO)


def expirada(status, enviada_em, agora=None):
    """Only a proposal still waiting for the client's answer can expire."""
    limite = valida_ate(enviada_em)
    if status != "enviada" or limite is None:
        return False
    return (agora or datetime.now(timezone.utc)) > limite


def corte_expiracao(agora=None):
    """Sent before this instant means expired now (same rule as ``expirada``, usable in SQL)."""
    hoje = (agora or datetime.now(timezone.utc)).astimezone(FUSO).date()
    return datetime.combine(hoje - timedelta(days=VALIDADE_DIAS), time(0, 0), tzinfo=FUSO)
