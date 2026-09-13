"""Phase C only: disposable DB, real HTML/QR/PDF and no external traffic."""
import unittest
import test_bootstrap_database as isolated
from test_proposta_service import SETUP

DOCUMENT_SETUP = SETUP + '''
import os, tempfile, base64
from io import BytesIO
from pathlib import Path
from pypdf import PdfReader
from services import pdf_service as pdf, proposta_documento_service as documents
from services.documento_storage import LocalDocumentoStorage, DocumentoIndisponivel
from services.qr_code_service import gerar_qr_code
storage_dir = tempfile.TemporaryDirectory(prefix='mirai-pdf-test-')
os.environ['PROPOSTA_PDF_DIR'] = storage_dir.name
network_guard = patch('socket.socket.connect', side_effect=AssertionError('network forbidden'))
network_guard.start()
'''


class DocumentoTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(DOCUMENT_SETUP + source)

    def test_qr_urls_and_resources(self):
        self.run_case('''
from PIL import Image
for url in ['https://example.com/pay?a=1&b=2', 'http://example.com/parcial']:
    image = Image.open(BytesIO(base64.b64decode(gerar_qr_code(url).split(',')[1])))
    assert image.format == 'PNG' and image.width > 200
    assert len(image.getcolors()) == 2
for url in ['', 'javascript:alert(1)', 'data:image/png,abc', 'file:///etc/passwd',
            'ftp://example.com', 'https://', 'https://user:password@example.com', 'https://example.com/a b']:
    try:
        gerar_qr_code(url)
    except ValueError:
        pass
    else:
        raise AssertionError('invalid URL accepted')
for url in ['https://example.com/image.png', 'file:///etc/passwd', '../secret.png']:
    try:
        pdf._recurso_local(url, '')
    except DocumentoIndisponivel:
        pass
    else:
        raise AssertionError('external resource accepted')
''')

    def test_generation_snapshot_money_and_invalidation(self):
        self.run_case('''
with Session(engine) as db:
    p = service.criar_por_orcamento(db, 1)
    p = service.atualizar(db, p.id, PropostaUpdate(descricao='<script>alert(1)</script> & teste',
        itens=[{'descricao': 'Mix & master', 'quantidade': 2, 'valor_unitario': '625.005', 'desconto': '0.01'}],
        pagamentos=[{'tipo': 'integral', 'titulo': 'Completo', 'url': 'https://example.com/pay', 'habilitado': True},
                    {'tipo': 'parcial_2', 'titulo': 'Final', 'url': 'https://example.com/final', 'habilitado': False}]))
    original = db.get(OrcamentoModel, 1)
    original.nome_cliente = 'DO NOT USE CURRENT BUDGET'
    db.commit()
    html = documents.preview(db, p.id)
    assert '&lt;script&gt;' in html and '<script>' not in html
    assert 'Cliente Teste' in html and 'DO NOT USE CURRENT BUDGET' not in html
    assert 'R$ 1.250,00' in html and 'https://example.com/final' not in html
    generated = documents.gerar_documento(db, p.id)
    assert generated.gerada_em and generated.pdf_path
    assert generated.versao == p.versao and generated.status == p.status
    data, filename = documents.obter_documento(db, p.id)
    reader = PdfReader(BytesIO(data))
    text = ''.join(page.extract_text() for page in reader.pages)
    assert '1.250,00' in text and 'Cliente Teste' in text
    assert sum(len(page.images) for page in reader.pages) >= 2
    assert db.get(OrcamentoModel, 1).status == 'novo'
    noop = service.atualizar(db, p.id, PropostaUpdate())
    assert noop.pdf_path == generated.pdf_path
    changed = service.atualizar(db, p.id, PropostaUpdate(descricao='Alteracao'))
    assert changed.pdf_path is None and changed.gerada_em is None
    assert changed.versao == p.versao + 1
    try:
        documents.obter_documento(db, p.id)
    except service.PropostaNaoEncontrada:
        pass
    else:
        raise AssertionError('stale PDF served')
''')

    def test_invalid_documents_and_failures_preserve_state(self):
        self.run_case('''
with Session(engine) as db:
    p = service.criar_por_orcamento(db, 1)
    for changes in [{'numero': ''}, {'itens': []}, {'itens': [PropostaItem(descricao='', quantidade=1, valor_unitario=1)]}]:
        try:
            pdf.renderizar_html(p.model_copy(update=changes), final=True)
        except service.PropostaInvalida:
            pass
        else:
            raise AssertionError('incomplete document accepted')
    from schemas.proposta import PropostaPagamento
    snapshot = p.cliente_snapshot.model_copy(deep=True)
    snapshot.cliente.nome = ''
    for changes in [
        {'cliente_snapshot': snapshot},
        {'pagamentos': [PropostaPagamento.model_construct(tipo='integral', titulo='Completo', url='', habilitado=True)]},
        {'pagamentos': [PropostaPagamento.model_construct(tipo='integral', titulo='Completo', url='javascript:alert(1)', habilitado=True)]}
    ]:
        try:
            pdf.renderizar_html(p.model_copy(update=changes), final=True)
        except service.PropostaInvalida:
            pass
        else:
            raise AssertionError('invalid snapshot/payment accepted')
    for target in ['renderizar_html', 'gerar_pdf']:
        with patch.object(pdf, target, side_effect=DocumentoIndisponivel('synthetic failure')):
            try:
                documents.gerar_documento(db, p.id)
            except DocumentoIndisponivel:
                pass
            else:
                raise AssertionError('failure hidden')
        assert service.buscar(db, p.id) == p
    with patch.object(db, 'commit', side_effect=SQLAlchemyError('synthetic failure')):
        try:
            documents.gerar_documento(db, p.id)
        except SQLAlchemyError:
            pass
    assert service.buscar(db, p.id) == p
    with patch.dict(os.environ, {'PROPOSTA_PDF_DIR': ''}):
        try:
            LocalDocumentoStorage()
        except DocumentoIndisponivel:
            pass
        else:
            raise AssertionError('implicit storage allowed')
    try:
        LocalDocumentoStorage().ler('../private.pdf')
    except DocumentoIndisponivel:
        pass
    else:
        raise AssertionError('path traversal accepted')
''')

    def test_layout_cases(self):
        self.run_case('''
with Session(engine) as db:
    p = service.criar_por_orcamento(db, 1)
    for count in [1, 2, 3]:
        long = count == 3
        item = {'descricao': 'Mixagem e masterizacao com revisoes tecnicas ' * (12 if long else 1),
                'quantidade': '2', 'valor_unitario': '1250000.50', 'desconto': '10.00'}
        p = service.atualizar(db, p.id, PropostaUpdate(
            descricao=('Descricao extensa do escopo. ' * 120 if long else 'Uma faixa.'),
            condicoes=('Condicoes comerciais detalhadas. ' * 180 if long else 'Prazo: 10 dias. Validade: 15 dias.'),
            itens=[item for _ in range(24 if long else 1)],
            pagamentos=[{'tipo': tipo, 'titulo': tipo, 'url': 'https://example.com/' + tipo, 'habilitado': True}
                        for tipo in ['integral', 'parcial_1', 'parcial_2'][:count]]))
        if long:
            snapshot = p.cliente_snapshot.model_copy(deep=True)
            snapshot.cliente.nome = 'Cliente Com Nome Muito Longo ' * 12
            p = p.model_copy(update={'cliente_snapshot': snapshot})
        html = pdf.renderizar_html(p, final=True)
        data = pdf.gerar_pdf(html)
        reader = PdfReader(BytesIO(data))
        text = ''.join(page.extract_text() for page in reader.pages)
        assert 'Assinatura:' in text and '2.499.991,00' in text
        assert ('parcial_2' in text) == (count == 3)
        assert len(reader.pages) >= (4 if long else 1)
        if os.environ.get('PROPOSTA_TEST_OUTPUT'):
            out = Path(os.environ['PROPOSTA_TEST_OUTPUT'])
            out.mkdir(parents=True, exist_ok=True)
            (out / f'layout-{count}.pdf').write_bytes(data)
            (out / f'layout-{count}.html').write_text(html, encoding='utf-8')
''')

    def test_document_routes(self):
        self.run_case('''
import asyncio, json
from fastapi import FastAPI
from routers.propostas import router, get_db, get_current_user
app = FastAPI()
app.include_router(router)
def session():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = session
app.dependency_overrides[get_current_user] = lambda: object()
with Session(engine) as db:
    p = service.criar_por_orcamento(db, 1)

async def request(method, path, data=None):
    body = json.dumps(data).encode() if data is not None else b''
    messages = []
    scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
             'method': method, 'scheme': 'http', 'path': path, 'raw_path': path.encode(),
             'query_string': b'', 'root_path': '', 'headers': [(b'content-type', b'application/json')],
             'client': ('127.0.0.1', 1234), 'server': ('test', 80)}
    async def receive():
        return {'type': 'http.request', 'body': body, 'more_body': False}
    async def send(message):
        messages.append(message)
    await app(scope, receive, send)
    start = next(m for m in messages if m['type'] == 'http.response.start')
    content = b''.join(m.get('body', b'') for m in messages if m['type'] == 'http.response.body')
    return start['status'], dict(start['headers']), content

async def check():
    network_guard.start()
    for suffix in ['preview', 'documento', 'gerar-documento']:
        status, _, _ = await request('POST' if suffix == 'gerar-documento' else 'GET', '/propostas/999/' + suffix)
        assert status == 404
    status, headers, html = await request('GET', f'/propostas/{p.id}/preview')
    assert status == 200 and b'text/html' in headers[b'content-type']
    assert b'Cliente Teste' in html and headers[b'cache-control'] == b'no-store'
    status, _, _ = await request('GET', f'/propostas/{p.id}/documento')
    assert status == 404
    status, _, body = await request('POST', f'/propostas/{p.id}/gerar-documento')
    generated = json.loads(body)
    assert status == 200 and generated['pdf_path'] and generated['gerada_em']
    assert generated['status'] == 'rascunho' and generated['versao'] == p.versao
    status, headers, content = await request('GET', f'/propostas/{p.id}/documento')
    assert status == 200 and content.startswith(b'%PDF-')
    assert headers[b'content-type'] == b'application/pdf'
    assert headers[b'cache-control'] == b'no-store'
    with patch.object(pdf.TEMPLATES, 'get_template', side_effect=RuntimeError('sensitive-sentinel')):
        status, _, body = await request('POST', f'/propostas/{p.id}/gerar-documento')
        assert status == 503 and b'sensitive-sentinel' not in body
    with patch.object(pdf.pisa, 'CreatePDF', side_effect=RuntimeError('sensitive-sentinel')):
        status, _, body = await request('POST', f'/propostas/{p.id}/gerar-documento')
        assert status == 503 and b'sensitive-sentinel' not in body
    status, _, _ = await request('PATCH', f'/propostas/{p.id}', {'itens': []})
    assert status == 200
    status, _, _ = await request('POST', f'/propostas/{p.id}/gerar-documento')
    assert status == 422
    status, _, _ = await request('GET', f'/propostas/{p.id}/documento')
    assert status == 404
# Windows creates a private socket pair while constructing the event loop.
network_guard.stop()
asyncio.run(check())
''')


if __name__ == '__main__':
    unittest.main()
