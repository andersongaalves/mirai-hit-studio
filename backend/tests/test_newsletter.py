"""Newsletter contracts in disposable SQLite; provider calls are always mocked."""

import unittest

import test_bootstrap_database as isolated


SETUP = r'''
import asyncio
from types import SimpleNamespace

import httpx
from fastapi import FastAPI
from sqlalchemy.orm import Session

from core.security import create_access_token, get_password_hash
from database import get_db
from models import AuditLogModel, ClienteModel, NewsletterModel, UsuarioModel
from routers.auth import router as auth_router
from routers.newsletter import router as newsletter_router

bootstrap(engine)
with Session(engine) as db:
    db.add_all([
        UsuarioModel(username='admin', password_hash=get_password_hash('admin-password'), role='admin', is_admin=True),
        UsuarioModel(username='produtor', password_hash=get_password_hash('producer-password'), role='produtor', is_admin=False),
    ])
    db.add(ClienteModel(nome='Cliente existente', email='cliente@example.com', ativo=True))
    db.commit()

app = FastAPI()
app.include_router(auth_router)
app.include_router(newsletter_router)
def session():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = session
def bearer(username):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': username})}
'''


class NewsletterTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_subscribers_campaigns_and_safe_delivery_history(self):
        self.run_case(r'''
def subscriber_token(identifier):
    with Session(engine) as db:
        return db.get(NewsletterModel, identifier).unsubscribe_token

async def check():
    from unittest.mock import patch
    from services.email_service import EmailService
    with patch.object(EmailService, 'enviar_boas_vindas', return_value={'id':'welcome'}) as welcome, \
         patch.object(EmailService, 'enviar_newsletter', side_effect=[{'id':'provider-one'}, None, None, None]) as send:
      async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        first = await client.post('/newsletter/subscribe', json={'email':' FIRST@EXAMPLE.COM ', 'nome':'Primeiro', 'source':'site_footer'})
        assert first.status_code == 200, first.text
        subscriber = first.json()
        assert subscriber['email'] == 'first@example.com' and subscriber['status'] == 'active'
        assert subscriber['consent_at'] and subscriber['source'] == 'site_footer'
        duplicate = await client.post('/newsletter', json={'email':'first@example.com'})
        assert duplicate.status_code == 200 and duplicate.json()['id'] == subscriber['id']
        assert welcome.call_count == 1
        assert (await client.get('/newsletter/unsubscribe?token=' + subscriber['email'])).status_code == 422
        assert (await client.post('/newsletter/unsubscribe', json={'token':'invalid-token'})).status_code == 422
        cancelled = await client.post('/newsletter/unsubscribe', json={'token': subscriber_token(subscriber['id'])})
        assert cancelled.status_code == 200 and cancelled.json()['status'] == 'unsubscribed'
        assert (await client.post('/newsletter/unsubscribe', json={'token': subscriber_token(subscriber['id'])})).status_code == 200
        resubscribed = await client.post('/newsletter/subscribe', json={'email':'first@example.com', 'source':'site_newsletter'})
        assert resubscribed.status_code == 200 and resubscribed.json()['id'] == subscriber['id'] and resubscribed.json()['status'] == 'active'
        second = await client.post('/newsletter/subscribe', json={'email':'second@example.com'})
        assert second.status_code == 200
        inactive = await client.post('/newsletter/subscribe', json={'email':'inactive@example.com'})
        assert inactive.status_code == 200
        assert (await client.post('/newsletter/unsubscribe', json={'token': subscriber_token(inactive.json()['id'])})).status_code == 200
        third = await client.post('/newsletter/subscribe', json={'email':'third@example.com'})
        assert third.status_code == 200
        with Session(engine) as db:
            assert db.query(ClienteModel).count() == 1

        assert (await client.get('/newsletter/subscribers')).status_code == 401
        assert (await client.get('/newsletter/subscribers', headers=bearer('produtor'))).status_code == 403
        listed = await client.get('/newsletter/subscribers?ativo=true', headers=bearer('admin'))
        assert listed.status_code == 200 and len(listed.json()) == 3
        assert (await client.patch(f"/newsletter/subscribers/{second.json()['id']}", headers=bearer('admin'), json={'ativo':False})).status_code == 200
        assert (await client.patch(f"/newsletter/subscribers/{second.json()['id']}", headers=bearer('admin'), json={'ativo':True})).status_code == 422

        payload = {'titulo_interno':'Novidades', 'assunto':'Assunto', 'preview_text':'Resumo', 'body_text':'Olá\n<script>alert(1)</script>'}
        assert (await client.post('/newsletter/campaigns', json=payload, headers=bearer('produtor'))).status_code == 403
        created = await client.post('/newsletter/campaigns', json=payload, headers=bearer('admin'))
        assert created.status_code == 201, created.text
        campaign = created.json()
        assert campaign['status'] == 'draft'
        edited = await client.patch(f"/newsletter/campaigns/{campaign['id']}", headers=bearer('admin'), json={'assunto':'Novo assunto'})
        assert edited.status_code == 200 and edited.json()['assunto'] == 'Novo assunto'
        detail = await client.get(f"/newsletter/campaigns/{campaign['id']}", headers=bearer('admin'))
        assert detail.json()['eligible_subscribers'] == 2
        sent = await client.post(f"/newsletter/campaigns/{campaign['id']}/send", headers=bearer('admin'))
        assert sent.status_code == 200, sent.text
        result = sent.json()
        assert result['status'] == 'sent' and result['total_sent'] == 1 and result['total_failed'] == 1
        assert len(result['deliveries']) == 2 and result['deliveries'][0]['recipient_email'] == 'first@example.com'
        assert send.call_count == 2
        assert (await client.post(f"/newsletter/campaigns/{campaign['id']}/send", headers=bearer('admin'))).status_code == 409
        assert (await client.patch(f"/newsletter/campaigns/{campaign['id']}", headers=bearer('admin'), json={'assunto':'Mutacao'})).status_code == 409

        failed_campaign = await client.post('/newsletter/campaigns', json={**payload, 'titulo_interno':'Falha'}, headers=bearer('admin'))
        failed = await client.post(f"/newsletter/campaigns/{failed_campaign.json()['id']}/send", headers=bearer('admin'))
        assert failed.status_code == 200 and failed.json()['status'] == 'failed' and failed.json()['total_failed'] == 2
        with Session(engine) as db:
            events = db.query(AuditLogModel).order_by(AuditLogModel.id).all()
            assert [event.action for event in events] == [
                'newsletter.subscriber_admin_unsubscribed',
                'newsletter.campaign_sent',
                'newsletter.campaign_sent',
            ]
            assert all(event.actor_user_id == 1 for event in events)
            assert all('body' not in str(event.metadata_json) and '@' not in str(event.metadata_json) for event in events)
        rendered = EmailService.render('email_campaign.html', preview_text='x', body_html=EmailService._texto_para_html('<script>x</script>'), unsubscribe_url='http://test/newsletter/unsubscribe?token=opaque')
        assert '&lt;script&gt;x&lt;/script&gt;' in rendered and '<script>x</script>' not in rendered
        assert 'Cancelar inscrição' in rendered and 'first@example.com' not in rendered
asyncio.run(check())
''')

    def test_migration_upgrade_downgrade_upgrade(self):
        isolated.BootstrapTests().run_case(r'''
from alembic import command
config = migration_config()
assert bootstrap(engine) == 'b7d3e9a1c5f2'
command.downgrade(config, 'c8f4e2d91a7b')
assert 'newsletter_campaigns' not in inspect(engine).get_table_names()
command.upgrade(config, 'head')
assert {'newsletter_campaigns', 'newsletter_deliveries'} <= set(inspect(engine).get_table_names())
columns = {column['name'] for column in inspect(engine).get_columns('newsletter')}
assert {'nome', 'consent_at', 'unsubscribed_at', 'unsubscribe_token', 'updated_at'} <= columns
''')


if __name__ == '__main__':
    unittest.main()
