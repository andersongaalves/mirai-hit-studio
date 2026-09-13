"""Explicit local adapter. Production must provide a persistent mounted directory."""
import os
import re
from pathlib import Path
from uuid import uuid4


class DocumentoIndisponivel(Exception):
    pass


class LocalDocumentoStorage:
    def __init__(self):
        directory = os.environ.get("PROPOSTA_PDF_DIR", "")
        if not directory or not Path(directory).is_absolute():
            raise DocumentoIndisponivel("Configure PROPOSTA_PDF_DIR com um diretorio absoluto persistente.")
        self.directory = Path(directory).resolve()

    def _path(self, key):
        if not re.fullmatch(r"proposta-\d+-v\d+-[a-f0-9]{32}\.pdf", key or ""):
            raise DocumentoIndisponivel("Referencia de documento invalida; gere o PDF novamente.")
        path = (self.directory / key).resolve()
        if path.parent != self.directory:
            raise DocumentoIndisponivel("Referencia de documento invalida.")
        return path

    def salvar(self, data, proposta_id, versao):
        key = f"proposta-{proposta_id}-v{versao}-{uuid4().hex}.pdf"
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            path = self._path(key)
            temporary = path.with_suffix(".tmp")
            with temporary.open("xb") as file:
                file.write(data)
                file.flush()
                os.fsync(file.fileno())
            temporary.replace(path)
        except OSError:
            raise DocumentoIndisponivel("Nao foi possivel armazenar o PDF.") from None
        return key

    def ler(self, key):
        try:
            return self._path(key).read_bytes()
        except OSError:
            raise DocumentoIndisponivel("PDF indisponivel no armazenamento; gere novamente.") from None
