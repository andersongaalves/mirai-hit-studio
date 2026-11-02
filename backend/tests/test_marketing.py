"""Admin "Marketing": lead origins, site records, Google Analytics parsing and access."""

import textwrap
import unittest

import test_bootstrap_database as isolated


class MarketingTests(unittest.TestCase):
    def run_case(self, code):
        isolated.BootstrapTests().run_case(textwrap.dedent(code))

    def test_lead_origin_site_records_and_unconfigured_providers(self):
        self.run_case("""
        import os
        bootstrap(engine)
        from datetime import datetime, timedelta, timezone
        from sqlalchemy.orm import Session
        from models import NewsletterModel, OrcamentoModel
        from schemas.orcamento import OrcamentoCreate
        from services import marketing_service as mkt, orcamento_service
        for name in ('GA4_PROPERTY_ID', 'GA4_SERVICE_ACCOUNT_JSON', 'CLOUDFLARE_API_TOKEN'):
            os.environ.pop(name, None)
        with Session(engine) as db:
            # The public form sends where the visit came from; it is stored as clean JSON.
            payload = {'nome_cliente': 'Ana', 'email': 'ana@example.com', 'servico': 'Mixagem', 'valor_total': 100,
                       'origem_marketing': {'utm_source': ' instagram ', 'utm_medium': 'social', 'utm_campaign': 'nov',
                                            'referrer': 'l.instagram.com', 'landing': '/artists',
                                            'primeiro_acesso': '2026-11-01T10:00:00Z', 'extra': 'ignored'}}
            created = orcamento_service.criar(db, OrcamentoCreate(**payload))
            assert created.origem_marketing == {'utm_source': 'instagram', 'utm_medium': 'social', 'utm_campaign': 'nov',
                                                'referrer': 'l.instagram.com', 'landing': '/artists',
                                                'primeiro_acesso': '2026-11-01T10:00:00Z'}, created.origem_marketing
            plain = orcamento_service.criar(db, OrcamentoCreate(nome_cliente='Bia', email='bia@example.com',
                                                                 servico='Beat', valor_total=50))
            assert plain.origem_marketing is None
            google = OrcamentoModel(nome_cliente='Caio', email='caio@example.com', servico='Mixagem',
                                    origem_marketing={'referrer': 'www.google.com', 'landing': '/'})
            old = OrcamentoModel(nome_cliente='Dan', email='dan@example.com', servico='Beat',
                                 data_solicitacao=datetime.now(timezone.utc) - timedelta(days=40))
            test = OrcamentoModel(nome_cliente='QA', email='qa@example.com', servico='Beat', is_test=True)
            db.add_all([google, old, test, NewsletterModel(email='n@example.com', origem='Footer')])
            db.commit()
            data = mkt.carregar(db, 28)
            assert data['google_analytics']['status'] == 'nao_configurado'
            assert data['google_analytics']['medicao'] == 'G-W4GLJXPRDM'
            assert data['cloudflare']['status'] == 'nao_configurado'
            site = data['site']
            assert site['status'] == 'ok', site
            leads = site['leads']
            assert leads['total'] == 3 and leads['com_origem'] == 2, leads
            origins = {item['nome']: item['quantidade'] for item in leads['por_origem']}
            assert origins == {'instagram / social': 1, 'Google (busca)': 1, 'Sem informação (anterior ao registro)': 1}, origins
            assert {item['nome'] for item in leads['por_servico']} == {'Mixagem', 'Beat'}
            assert leads['por_campanha'] == [{'nome': 'nov', 'quantidade': 1}]
            assert {item['nome'] for item in leads['paginas_de_entrada']} == {'/artists', '/'}
            assert len(leads['serie']) == 28 and sum(item['leads'] for item in leads['serie']) == 3
            assert site['funil'][0] == {'etapa': 'Pedidos de orçamento', 'quantidade': 3}
            assert site['newsletter']['novos'] == 1
            # Cached for ten minutes unless asked to refresh.
            assert mkt.carregar(db, 28) is data
            assert mkt.carregar(db, 28, atualizar=True) is not data
            # Unknown periods fall back to 28 days.
            assert mkt.carregar(db, 5)['dias'] == 28
        for referrer, expected in (('m.facebook.com', 'Facebook'), ('t.co', 'X / Twitter'), ('wa.me', 'WhatsApp'),
                                   ('blog.example.com', 'blog.example.com'), ('miraihitstudio.com.br', 'Direto'), (None, 'Direto')):
            assert mkt._origem_lead({'referrer': referrer} if referrer else {'landing': '/'}) == expected, referrer
        # A malformed credential is reported, never a crash.
        os.environ['GA4_PROPERTY_ID'] = '123'
        os.environ['GA4_SERVICE_ACCOUNT_JSON'] = 'not-json'
        assert mkt._google_analytics(7)['status'] == 'erro'
        """)

    def test_google_analytics_reports_are_parsed(self):
        self.run_case("""
        import json, os
        from unittest.mock import patch
        from services import marketing_service as mkt
        os.environ['GA4_PROPERTY_ID'] = 'properties/123'
        os.environ['GA4_SERVICE_ACCOUNT_JSON'] = json.dumps({'client_email': 'sa@example.iam.gserviceaccount.com',
                                                             'private_key': 'unused-in-test'})
        def report(dims, mets, rows):
            return {'dimensionHeaders': [{'name': name} for name in dims], 'metricHeaders': [{'name': name} for name in mets],
                    'rows': [{'dimensionValues': [{'value': value} for value in row[0]],
                              'metricValues': [{'value': str(value)} for value in row[1]]} for row in rows]}
        totals = ['activeUsers', 'newUsers', 'sessions', 'screenPageViews', 'engagementRate', 'averageSessionDuration']
        batches = [
            {'reports': [
                report(['dateRange'], totals, [(['date_range_0'], [120, 90, 150, 400, 0.5, 60.5]), (['date_range_1'], [100, 80, 160, 300, 0.4, 50])]),
                report(['date'], ['activeUsers', 'sessions'], [(['20261101'], [10, 12]), (['20261102'], [20, 25])]),
                report(['sessionDefaultChannelGroup'], ['sessions', 'activeUsers'], [(['Organic Social'], [70, 60])]),
                report(['sessionSourceMedium'], ['sessions', 'activeUsers'], [(['instagram.com / referral'], [60, 50])]),
                report(['pagePath'], ['screenPageViews', 'activeUsers'], [(['/'], [200, 90])]),
            ]},
            {'reports': [
                report(['country'], ['activeUsers'], [(['Brazil'], [110])]),
                report(['city'], ['activeUsers'], [(['São Paulo'], [50])]),
                report(['deviceCategory'], ['activeUsers'], [(['mobile'], [90])]),
                report(['eventName'], ['eventCount'], [(['generate_lead'], [4])]),
                report(['sessionCampaignName'], ['sessions', 'activeUsers'], [(['nov'], [30, 25])]),
            ]},
            report([], ['activeUsers'], [([], [3])]),
        ]
        calls = []
        def fake_post(path, body, token):
            calls.append((path, body))
            return batches[len(calls) - 1]
        with patch.object(mkt, '_ga_token', return_value='token'), patch.object(mkt, '_ga_post', side_effect=fake_post):
            data = mkt._google_analytics(7)
        assert data['status'] == 'ok', data
        assert [path for path, _ in calls] == ['properties/123:batchRunReports', 'properties/123:batchRunReports',
                                               'properties/123:runRealtimeReport']
        assert len(calls[0][1]['requests']) == 5 and len(calls[1][1]['requests']) == 5
        assert data['totais']['activeUsers'] == 120 and data['anterior']['activeUsers'] == 100
        assert data['totais']['averageSessionDuration'] == 60.5
        assert data['serie'] == [{'data': '2026-11-01', 'visitantes': 10, 'sessoes': 12}, {'data': '2026-11-02', 'visitantes': 20, 'sessoes': 25}]
        assert data['canais'] == [{'nome': 'Organic Social', 'sessoes': 70, 'visitantes': 60}]
        assert data['agora_no_site'] == 3
        events = {item['nome']: item['quantidade'] for item in data['eventos']}
        assert events['generate_lead'] == 4 and events['begin_checkout'] == 0
        # Access denied on the property is explained.
        with patch.object(mkt, '_ga_token', return_value='token'), patch.object(mkt, '_ga_post', side_effect=PermissionError('x')):
            assert 'Leitor' in mkt._google_analytics(7)['mensagem']
        """)

    def test_marketing_route_is_admin_only(self):
        self.run_case("""
        bootstrap(engine)
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from core.dependencies import require_admin
        from routers.marketing import router
        from types import SimpleNamespace
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        assert client.get('/admin/marketing').status_code in (401, 403)
        app.dependency_overrides[require_admin] = lambda: SimpleNamespace(id=1, is_admin=True, role='admin')
        response = client.get('/admin/marketing', params={'dias': 7})
        assert response.status_code == 200, response.text
        assert response.json()['dias'] == 7 and response.json()['site']['status'] == 'ok'
        assert client.get('/admin/marketing', params={'dias': 5}).status_code == 422
        """)


if __name__ == "__main__":
    unittest.main()
