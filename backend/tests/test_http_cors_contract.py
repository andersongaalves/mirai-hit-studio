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


if __name__ == "__main__":
    unittest.main()
