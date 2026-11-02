"""Cross-origin contract between Cloudflare Pages and the Render API (AUD-S12-002)."""

import textwrap
import unittest

import test_bootstrap_database as isolated


class CrossOriginDownloadContractTests(unittest.TestCase):
    def test_browser_can_read_download_filename_and_request_id(self):
        isolated.BootstrapTests().run_case(textwrap.dedent("""
        bootstrap(engine)
        import main
        from fastapi.testclient import TestClient
        client = TestClient(main.app)
        response = client.get('/health', headers={'Origin': 'http://localhost'})
        assert response.status_code == 200, response.text
        assert response.headers['access-control-allow-origin'] == 'http://localhost'
        exposed = {
            item.strip().lower()
            for item in response.headers['access-control-expose-headers'].split(',')
        }
        # Portals read Content-Disposition to save files with their real names.
        assert {'content-disposition', 'x-request-id'} <= exposed, exposed
        """))

    def test_direct_render_address_only_takes_uploads(self):
        isolated.BootstrapTests().run_case(textwrap.dedent("""
        bootstrap(engine)
        import main
        from fastapi.testclient import TestClient
        direct = TestClient(main.app, base_url='https://mirai-hit-studio.onrender.com')
        api = TestClient(main.app, base_url='https://api.miraihitstudio.com.br')
        # Through Cloudflare (API subdomain) everything is served as before.
        assert api.get('/servicos').status_code == 200
        # The direct address refuses regular calls with a pointer to the API subdomain...
        refused = direct.get('/servicos')
        assert refused.status_code == 421 and 'api.miraihitstudio.com.br' in refused.json()['detail'], refused.text
        assert direct.post('/auth/login', json={'username': 'x', 'password': 'y'}).status_code == 421
        assert direct.get('/portal/produtor/producoes').status_code == 421
        # ...but keeps health, signed webhooks, unsubscribe links and every form (upload) route.
        assert direct.get('/health').status_code == 200
        assert direct.post('/webhooks/mercado-pago', json={}).status_code != 421
        assert direct.get('/newsletter/unsubscribe', params={'token': 'x' * 32}).status_code != 421
        for method, path in (('POST', '/portal/produtor/beats'), ('PUT', '/portal/produtor/beats/1'),
                             ('POST', '/portal/produtor/producoes/1/entregas-finais'),
                             ('POST', '/portal/produtor/producoes/1/arquivos')):
            status = direct.request(method, path, files={'x': ('a.bin', b'a')}).status_code
            assert status != 421, (method, path, status)
        # A form route under another method is not opened by accident.
        assert direct.delete('/portal/produtor/beats/1').status_code == 421
        preflight = direct.options('/portal/produtor/beats', headers={
            'Origin': 'http://localhost', 'Access-Control-Request-Method': 'POST'})
        assert preflight.status_code != 421
        """))


if __name__ == "__main__":
    unittest.main()
