"""Pausing new quote requests from the Admin (busy schedule)."""

import textwrap
import unittest

import test_bootstrap_database as isolated


class OrcamentosPausaTests(unittest.TestCase):
    def run_case(self, code):
        isolated.BootstrapTests().run_case(textwrap.dedent(code))

    def test_admin_pauses_and_resumes_quote_requests(self):
        self.run_case("""
        import asyncio
        from unittest.mock import patch
        import httpx
        from sqlalchemy.orm import Session
        from core.security import create_access_token
        from models import AuditLogModel, ConfigModel, OrcamentoModel, UsuarioModel
        from services import orcamento_pausa_service
        bootstrap(engine)
        with Session(engine) as db:
            db.add(UsuarioModel(id=1, username='admin', password_hash='x', role='admin', is_admin=True, ativo=True))
            db.commit()
        import main
        admin = {'Authorization': 'Bearer ' + create_access_token({'sub': 'admin', 'av': 0, 'uid': 1})}
        payload = {'nome_cliente': 'Ana', 'email': 'ana@example.com', 'whatsapp': '11 99999-0000',
                   'servico': 'Personalizado', 'valor_total': None, 'detalhes': 'Descrição: trilha para jogo.'}
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://test') as api:
                # Open by default, even without a saved configuration row.
                status = await api.get('/orcamentos/disponibilidade')
                assert status.json() == {'pausado': False, 'mensagem': None}
                assert status.headers['cache-control'] == 'no-store'
                assert (await api.get('/orcamentos/recebimento')).status_code == 401
                assert (await api.put('/orcamentos/recebimento', json={'pausado': True})).status_code == 401
                # Pausing: the public status and new requests both reflect it.
                paused = await api.put('/orcamentos/recebimento', headers=admin, json={'pausado': True, 'mensagem': ''})
                assert paused.status_code == 200, paused.text
                assert paused.json()['pausado'] is True and paused.json()['desde'] is not None
                status = (await api.get('/orcamentos/disponibilidade')).json()
                assert status['pausado'] is True and status['mensagem'] == orcamento_pausa_service.MENSAGEM_PADRAO
                with patch('services.email_service.EmailService.enviar_confirmacao'), \\
                        patch('services.email_service.EmailService.enviar_notificacao_admin'):
                    refused = await api.post('/orcamentos', json=payload)
                    assert refused.status_code == 503, refused.text
                    assert refused.headers['x-mirai-orcamentos'] == 'pausados'
                    # A custom message replaces the default one.
                    await api.put('/orcamentos/recebimento', headers=admin,
                                  json={'pausado': True, 'mensagem': '  Agenda   cheia até dezembro.  '})
                    assert (await api.get('/orcamentos/disponibilidade')).json()['mensagem'] == 'Agenda cheia até dezembro.'
                    assert (await api.post('/orcamentos', json=payload)).json()['detail'] == 'Agenda cheia até dezembro.'
                    # Resuming accepts requests again; a custom service without catalog price is fine.
                    resumed = await api.put('/orcamentos/recebimento', headers=admin, json={'pausado': False})
                    assert resumed.json()['pausado'] is False and resumed.json()['desde'] is None
                    created = await api.post('/orcamentos', json=payload)
                    assert created.status_code == 200, created.text
                    assert created.json()['servico'] == 'Personalizado' and created.json()['valor_total'] is None
            with Session(engine) as db:
                assert db.query(OrcamentoModel).count() == 1
                actions = [row.action for row in db.query(AuditLogModel).order_by(AuditLogModel.id)]
                assert actions.count('budget.intake_paused') == 2 and actions.count('budget.intake_resumed') == 1
        asyncio.run(check())
        """)


if __name__ == "__main__":
    unittest.main()
