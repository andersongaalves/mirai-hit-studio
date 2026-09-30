"""Durable proposal storage tests; all provider traffic is synthetic."""
import unittest

import httpx

import test_bootstrap_database as isolated
from services.documento_storage import DocumentoIndisponivel, SupabaseDocumentoStorage
from test_proposta_comercial import SETUP


class SupabaseStorageAdapterTests(unittest.TestCase):
    def test_private_bucket_upload_download_and_no_upsert(self):
        objects = {}
        requests = []

        def handler(request):
            requests.append(request)
            if request.url.path.endswith("/bucket/propostas-pdf"):
                return httpx.Response(200, json={"id": "propostas-pdf", "public": False})
            if "/object/authenticated/propostas-pdf/" in request.url.path:
                key = request.url.path.split("/object/authenticated/propostas-pdf/", 1)[1]
                return httpx.Response(200, content=objects[key])
            if "/object/propostas-pdf/" in request.url.path:
                key = request.url.path.split("/object/propostas-pdf/", 1)[1]
                self.assertEqual(request.headers["x-upsert"], "false")
                self.assertNotIn("cliente", key.lower())
                self.assertNotIn("@", key)
                if key in objects:
                    return httpx.Response(409)
                objects[key] = request.content
                return httpx.Response(200, json={"Key": key})
            return httpx.Response(404)

        storage = SupabaseDocumentoStorage(
            base_url="https://project.supabase.co",
            service_key="test-server-only",
            bucket="propostas-pdf",
            transport=httpx.MockTransport(handler),
        )
        data = b"%PDF-1.4\nsynthetic"
        reference = storage.salvar(data, 12, 3)
        self.assertRegex(reference, r"^supabase://propostas-pdf/propostas/12/v3/[a-f0-9]{32}\.pdf$")
        self.assertEqual(storage.ler(reference), data)
        self.assertTrue(all("test-server-only" not in str(request.url) for request in requests))

    def test_bucket_is_created_private_and_public_bucket_is_rejected(self):
        state = {"exists": False}

        def create_handler(request):
            if request.method == "GET":
                return httpx.Response(200 if state["exists"] else 404,
                                      json={"public": False} if state["exists"] else None)
            if request.method == "POST" and request.url.path.endswith("/bucket"):
                payload = request.read().decode()
                self.assertIn('"public":false', payload.replace(" ", ""))
                self.assertIn("application/pdf", payload)
                state["exists"] = True
                return httpx.Response(200)
            if request.method == "POST" and "/object/" in request.url.path:
                return httpx.Response(200)
            return httpx.Response(404)

        storage = SupabaseDocumentoStorage(
            base_url="https://project.supabase.co", service_key="server-only",
            bucket="propostas-pdf", transport=httpx.MockTransport(create_handler),
        )
        storage.salvar(b"%PDF-test", 1, 1)
        self.assertTrue(state["exists"])

        public = SupabaseDocumentoStorage(
            base_url="https://project.supabase.co", service_key="server-only",
            bucket="propostas-pdf",
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"public": True})),
        )
        with self.assertRaises(DocumentoIndisponivel):
            public.salvar(b"%PDF-test", 1, 1)

    def test_upload_failure_is_sanitized(self):
        def handler(request):
            if "/bucket/" in request.url.path:
                return httpx.Response(200, json={"public": False})
            return httpx.Response(500, json={"message": "secret-provider-detail"})

        storage = SupabaseDocumentoStorage(
            base_url="https://project.supabase.co", service_key="server-only",
            bucket="propostas-pdf", transport=httpx.MockTransport(handler),
        )
        with self.assertRaises(DocumentoIndisponivel) as raised:
            storage.salvar(b"%PDF-test", 1, 1)
        self.assertNotIn("secret-provider-detail", str(raised.exception))
        self.assertNotIn("server-only", str(raised.exception))


class ProposalDurabilityTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_upload_reuse_hash_and_immutability_after_send(self):
        self.run_case('''
import hashlib
class MemoryStorage:
    def __init__(self):
        self.objects = {}
        self.saves = 0
        self.reads = 0
    def salvar(self, data, proposta_id, versao):
        self.saves += 1
        key = f'supabase://propostas-pdf/propostas/{proposta_id}/v{versao}/' + ('a' * 32) + '.pdf'
        assert key not in self.objects
        self.objects[key] = data
        return key
    def ler(self, key):
        self.reads += 1
        return self.objects[key]
storage = MemoryStorage()
with Session(engine) as db, \\
     patch.object(documents, 'novo_documento_storage', return_value=storage), \\
     patch.object(documents, 'storage_para_referencia', return_value=storage):
    p = service.criar_por_orcamento(db, 1)
    generated = documents.gerar_documento(db, p.id)
    model = db.get(PropostaModel, p.id)
    original_key = model.pdf_path
    original_data = storage.objects[original_key]
    assert model.pdf_sha256 == hashlib.sha256(original_data).hexdigest()
    with patch.object(resend.Emails, 'send', return_value={'id':'synthetic-message'}) as send:
        sent = commercial.enviar(db, p.id)
        assert storage.saves == 1
        attachment = base64.b64decode(send.call_args.args[0]['attachments'][0]['content'])
        assert attachment == original_data
        documents.gerar_documento(db, p.id)
        assert storage.saves == 1 and db.get(PropostaModel, p.id).pdf_path == original_key
        commercial.enviar(db, p.id)
        assert send.call_count == 1
    assert sent.pdf_path == original_key
''')

    def test_upload_failure_does_not_send_or_mark_sent(self):
        self.run_case('''
class FailingStorage:
    def salvar(self, data, proposta_id, versao):
        raise DocumentoIndisponivel('synthetic storage failure')
with Session(engine) as db:
    p = service.criar_por_orcamento(db, 1)
    with patch.object(documents, 'novo_documento_storage', return_value=FailingStorage()), \\
         patch.object(resend.Emails, 'send') as send:
        try:
            commercial.enviar(db, p.id)
        except DocumentoIndisponivel:
            pass
        else:
            raise AssertionError('storage failure hidden')
        send.assert_not_called()
    model = db.get(PropostaModel, p.id)
    assert model.status == 'rascunho' and model.enviada_em is None
    assert model.pdf_path is None and model.pdf_sha256 is None
''')

    def test_legacy_local_document_is_uploaded_without_regeneration(self):
        self.run_case('''
import hashlib
class MemoryStorage:
    def __init__(self): self.objects = {}
    def salvar(self, data, proposta_id, versao):
        key = f'supabase://propostas-pdf/propostas/{proposta_id}/v{versao}/' + ('b' * 32) + '.pdf'
        self.objects[key] = data
        return key
    def ler(self, key): return self.objects[key]
storage = MemoryStorage()
with Session(engine) as db:
    p = service.criar_por_orcamento(db, 1)
    p = documents.gerar_documento(db, p.id)
    model = db.get(PropostaModel, p.id)
    legacy_key = model.pdf_path
    legacy_data = LocalDocumentoStorage().ler(legacy_key)
    model.pdf_sha256 = None
    db.commit()
    with patch.object(documents, 'novo_documento_storage', return_value=storage), \\
         patch.object(documents.pdf_service, 'gerar_pdf', side_effect=AssertionError('legacy PDF regenerated')), \\
         patch.object(resend.Emails, 'send', return_value={'id':'synthetic-message'}) as send:
        commercial.enviar(db, p.id)
    model = db.get(PropostaModel, p.id)
    assert model.pdf_path != legacy_key and model.pdf_path in storage.objects
    assert storage.objects[model.pdf_path] == legacy_data
    assert model.pdf_sha256 == hashlib.sha256(legacy_data).hexdigest()
    assert base64.b64decode(send.call_args.args[0]['attachments'][0]['content']) == legacy_data
''')


if __name__ == "__main__":
    unittest.main()
