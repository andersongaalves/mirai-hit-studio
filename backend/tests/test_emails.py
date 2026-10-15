"""E-mail templates audit (15/10/2026): content consistent with the current system."""
import unittest

import test_bootstrap_database as isolated

SETUP = '''
import re
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
import resend
from core.config import settings
from services import client_access_service
from services.email_service import EmailService, _data_br, _moeda

settings.PUBLIC_FRONTEND_URL = 'https://site.example/'
sent = []
def capture(payload, options=None):
    sent.append(payload)
    return {'id': 'synthetic'}
client = SimpleNamespace(nome='Ana <b>Lima</b>', email='ana@example.com')

def check_common(html):
    assert 'youtube.com' not in html and 'https://miraihitstudio.com.br' not in html, 'hard-coded or placeholder links'
    assert 'https://site.example/img/logo-horizontal.png' in html and 'https://site.example/portfolio.html' in html
    assert 'R$ R$' not in html and 'R$ A definir' not in html
    assert '<b>Lima</b>' not in html
'''


class EmailTemplateTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_helpers(self):
        self.run_case('''
assert _moeda(1250) == 'R$ 1.250,00' and _moeda(0.5) == 'R$ 0,50' and _moeda(None) == 'A definir'
assert _data_br(datetime(2026, 10, 15, 13, 5, tzinfo=timezone.utc)) == '15/10/2026 10:05'
assert _data_br(datetime(2026, 10, 15, 2, 0)) == '14/10/2026 23:00'  # Naive values are UTC.
''')

    def test_quote_confirmation_and_admin_notice(self):
        self.run_case('''
budget = SimpleNamespace(nome_cliente='Ana <b>Lima</b>', email='ana@example.com', whatsapp=None, servico='Mixagem',
                         valor_total=1234.5, data_solicitacao=datetime(2026, 10, 15, 13, 5, tzinfo=timezone.utc),
                         detalhes='Quero <script>x</script>')
with patch.object(resend.Emails, 'send', side_effect=capture):
    EmailService.enviar_confirmacao(budget, 'MHS-000123')
    EmailService.enviar_notificacao_admin(budget, 'MHS-000123')
    EmailService.enviar_confirmacao(SimpleNamespace(**{**budget.__dict__, 'valor_total': None}), 'MHS-000124')
client_mail, admin_mail, no_value = sent
html = client_mail['html']
check_common(html)
assert html.count('Valor estimado') == 1 and html.count('Data da solicitação') == 1  # No duplicated blocks.
assert 'R$ 1.234,50' in html and '15/10/2026 10:05' in html
assert 'Portal do Cliente' in html and 'WhatsApp informado' not in html
assert '<script>x</script>' not in html and '&lt;script&gt;' in html
assert 'A definir' in no_value['html']
assert 'Não informado' in admin_mail['html'] and 'None' not in admin_mail['html']
assert 'https://site.example/admin' in admin_mail['html'] and 'R$ 1.234,50' in admin_mail['html']
''')

    def test_proposal_and_portal_access(self):
        self.run_case('''
proposal = SimpleNamespace(cliente_snapshot=SimpleNamespace(cliente=client), numero='MHS-000123', objeto='Mixagem',
                           descricao='', politica_pagamento='entrada_50_50', id=7, versao=2,
                           created_at=datetime(2026, 10, 15, tzinfo=timezone.utc))
with patch.object(resend.Emails, 'send', side_effect=capture):
    EmailService.enviar_proposta(proposal, b'%PDF-1.4', 'R$ 1.250,00')
    EmailService.enviar_proposta_disponivel(client, 'https://site.example/portal-cliente.html#p7', proposta_numero='MHS-000123', idempotency_key='k1')
    EmailService.enviar_convite_cliente(client, 'https://site.example/ativar.html#t', idempotency_key='k2')
    EmailService.enviar_confirmacao_cadastro(client, 'https://site.example/ativar.html#c', idempotency_key='k3')
    EmailService.enviar_recuperacao_senha(client, 'https://site.example/redefinir-senha.html#r', idempotency_key='k4')
pdf_mail, portal_mail, invite, signup, recovery = sent
for mail in sent:
    check_common(mail['html'])
# The proposal no longer tells the client to accept by contacting the team: it is the portal.
assert 'R$ 1.250,00' in pdf_mail['html'] and 'Portal do Cliente' in pdf_mail['html']
assert '50% para iniciar' in pdf_mail['html'] and 'confirmar o aceite, entre em contato' not in pdf_mail['html']
assert 'https://site.example/acesso"' in pdf_mail['html'] and pdf_mail['attachments']
assert portal_mail['subject'] == 'Proposta MHS-000123 disponível no Portal do Cliente'
assert 'aceitar ou recusar' in portal_mail['html']
hours = int(client_access_service.INVITE_TTL.total_seconds() // 3600)
minutes = int(client_access_service.RECOVERY_TTL.total_seconds() // 60)
assert f'expira em {hours} horas' in invite['html'] and f'expira em {hours} horas' in signup['html']
assert f'válido por {minutes} minutos' in recovery['html']
assert invite['subject'] == 'Ative seu acesso ao Portal do Cliente Mirai'
# Every transactional e-mail uses the shared layout (header, footer, unsubscribe-free).
assert all('Criando hits do futuro.' in mail['html'] for mail in sent)
''')

    def test_newsletter_welcome_and_campaign(self):
        self.run_case('''
subscriber = SimpleNamespace(nome='', email='joao.silva@example.com', unsubscribe_token='opaque')
campaign = SimpleNamespace(preview_text='', body_text='Linha 1', assunto='Novidades')
with patch.object(resend.Emails, 'send', side_effect=capture):
    EmailService.enviar_boas_vindas(subscriber)
    EmailService.enviar_newsletter(subscriber, campaign)
welcome, news = sent
check_common(welcome['html'])
assert 'Joao Silva' in welcome['html'] and 'Cancelar inscrição' in welcome['html']
assert news['text'].endswith('Cancelar inscrição: ' + EmailService._url_cancelamento('opaque'))
''')


if __name__ == "__main__":
    unittest.main()
