"""Duration of an uploaded audio file (catalog rework: max minutes per track).

Reads only the container metadata with mutagen (MP3, WAV, FLAC, M4A/AAC); nothing is
decoded or executed. Returns None when the duration cannot be read.
"""
from io import BytesIO

try:
    import mutagen
except ImportError:  # pragma: no cover - the dependency is in requirements.txt.
    mutagen = None


def segundos(data: bytes) -> float | None:
    if mutagen is None or not data:
        return None
    try:
        arquivo = mutagen.File(BytesIO(data))
    except Exception:  # noqa: BLE001 - any parser error means "unreadable".
        return None
    duracao = getattr(getattr(arquivo, "info", None), "length", None)
    if not isinstance(duracao, (int, float)) or duracao <= 0:
        return None
    return float(duracao)
