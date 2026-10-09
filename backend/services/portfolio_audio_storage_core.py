"""Portfolio-audio facade backed by the provider-neutral Storage Core."""

from __future__ import annotations

from services.portfolio_audio_storage import PortfolioAudioStorageError

from .storage.contracts import ObjectReference, StorageError, StorageScope
from .storage.registry import storage_for


class PortfolioAudioStorage:
    def __init__(self, adapter=None) -> None:
        try:
            self.adapter = adapter or storage_for(StorageScope.PORTFOLIO_AUDIO)
        except StorageError as error:
            raise PortfolioAudioStorageError(str(error)) from None

    def _reference(self, value: str) -> ObjectReference:
        try:
            if "://" in value:
                return ObjectReference.parse(value)
            if self.adapter.provider != "supabase" or not getattr(self.adapter, "bucket", None):
                raise PortfolioAudioStorageError("Referencia de audio legada indisponivel.")
            return ObjectReference("supabase", self.adapter.bucket, value)
        except StorageError as error:
            raise PortfolioAudioStorageError(str(error)) from None

    def save(self, data: bytes, project_id: int, slot: str) -> str:
        if slot not in {"before", "after"}:
            raise PortfolioAudioStorageError("Slot de audio invalido.")
        try:
            stored = self.adapter.save(
                data,
                "audio/mpeg",
                metadata={"project_id": str(project_id), "slot": slot},
            )
            return str(stored.reference)
        except StorageError as error:
            raise PortfolioAudioStorageError(str(error)) from None

    def delete(self, value: str) -> None:
        try:
            self.adapter.delete(self._reference(value))
        except StorageError as error:
            raise PortfolioAudioStorageError(str(error)) from None

    def public_url(self, value: str) -> str:
        try:
            return self.adapter.get_public_url(self._reference(value))
        except StorageError as error:
            raise PortfolioAudioStorageError(str(error)) from None


def new_portfolio_audio_storage() -> PortfolioAudioStorage:
    return PortfolioAudioStorage()
