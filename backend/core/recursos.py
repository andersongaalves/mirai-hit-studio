"""AUD6-S12-002: container memory as seen by the process (Render runs it in a cgroup)."""
from pathlib import Path

_CGROUP_V2 = Path("/sys/fs/cgroup")
_CGROUP_V1 = Path("/sys/fs/cgroup/memory")


def _ler_int(path):
    try:
        value = path.read_text().strip()
    except OSError:
        return None
    if not value or value == "max":
        return None
    try:
        number = int(value)
    except ValueError:
        return None
    # cgroup v1 reports a huge sentinel when there is no limit.
    return None if number >= 1 << 60 else number


def memoria():
    """Returns {"usada_bytes", "limite_bytes"} or Nones when the platform does not expose them."""
    usada = _ler_int(_CGROUP_V2 / "memory.current")
    limite = _ler_int(_CGROUP_V2 / "memory.max")
    if usada is None:
        usada = _ler_int(_CGROUP_V1 / "memory.usage_in_bytes")
        limite = _ler_int(_CGROUP_V1 / "memory.limit_in_bytes")
    return {"usada_bytes": usada, "limite_bytes": limite}


def memoria_apertada(limiar=0.8):
    """True only when both values are known and usage is above the threshold."""
    dados = memoria()
    if not dados["usada_bytes"] or not dados["limite_bytes"]:
        return False
    return dados["usada_bytes"] / dados["limite_bytes"] >= limiar
