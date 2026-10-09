"""Administrative portfolio-image uploads with disposable storage."""

import unittest

import test_bootstrap_database as isolated


class PortfolioImageStorageTests(unittest.TestCase):
    def test_admin_upload_replace_delete_and_validation(self):
        isolated.BootstrapTests().run_case(r'''
import asyncio
from unittest.mock import patch

import httpx
from sqlalchemy.orm import Session

from core.security import create_access_token, get_password_hash
from models import ConfigModel, UsuarioModel
from services.storage.contracts import StorageScope
from services.storage.memory import InMemoryStorage

bootstrap(engine)
with Session(engine) as db:
    db.add(ConfigModel(id=1, portfolio_segments_json=[]))
    db.add(UsuarioModel(
        username="admin", password_hash=get_password_hash("password-test"),
        is_admin=True, role="admin"))
    db.commit()

import main

headers = {"Authorization": "Bearer " + create_access_token({"sub": "admin", "av": 0})}
payload = {
    "titulo": "Capa sintetica", "artista": "Artista", "categoria": "Mixagem",
    "link_audio": "https://example.invalid/audio",
    "link_capa": "https://example.invalid/legacy.webp",
    "descricao": "Fixture", "destaque": False,
    "vertical": "artists", "segmentos_json": [], "case_type": "demo",
}

class PublicImageFake(InMemoryStorage):
    def __init__(self):
        super().__init__(StorageScope.PUBLIC_IMAGE)

    def reference_from_public_url(self, value):
        for key in self.objects:
            reference = self._reference(key)
            if self.get_public_url(reference) == value:
                return reference
        return None

storage = PublicImageFake()

async def check():
    transport = httpx.ASGITransport(app=main.app)
    with patch("routers.projetos.storage_for", return_value=storage):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post("/projetos", headers=headers, json=payload)
            assert created.status_code == 200, created.text
            project_id = created.json()["id"]

            unauthenticated = await client.post(
                f"/projetos/{project_id}/imagem",
                files={"imagem": ("cover.png", b"\x89PNG\r\n\x1a\nfirst", "image/png")})
            assert unauthenticated.status_code == 401

            first = await client.post(
                f"/projetos/{project_id}/imagem", headers=headers,
                files={"imagem": ("private-name.png", b"\x89PNG\r\n\x1a\nfirst", "image/png")})
            assert first.status_code == 200, first.text
            first_url = first.json()["link_capa"]
            assert first_url.startswith("https://storage.example.invalid/public-image/")
            assert "private-name" not in first_url and len(storage.objects) == 1

            invalid = await client.post(
                f"/projetos/{project_id}/imagem", headers=headers,
                files={"imagem": ("fake.png", b"not-an-image", "image/png")})
            assert invalid.status_code == 422
            assert len(storage.objects) == 1

            second = await client.post(
                f"/projetos/{project_id}/imagem", headers=headers,
                files={"imagem": ("replacement.webp", b"RIFFxxxxWEBPdata", "image/webp")})
            assert second.status_code == 200, second.text
            assert second.json()["link_capa"] != first_url
            assert len(storage.objects) == 1 and len(storage.deleted) == 1

            removed = await client.delete(f"/projetos/{project_id}/imagem", headers=headers)
            assert removed.status_code == 200 and removed.json()["link_capa"] == ""
            assert storage.objects == {} and len(storage.deleted) == 2

asyncio.run(check())
''')


if __name__ == "__main__":
    unittest.main()
