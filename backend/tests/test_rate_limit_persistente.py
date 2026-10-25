"""Etapa 07, APL-S12-03 and APL-S02-07: shared, persistent request limits."""
import unittest

import test_bootstrap_database as isolated

SETUP = r'''
import asyncio, os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import httpx
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from core.security import get_password_hash
from database import get_db
from models import UsuarioModel
from routers.auth import router as auth_router
from services import rate_limit_service as limits
os.environ['RATE_LIMIT_DB'] = config.settings.BACKUP_FOLDER + '/local-limits.sqlite3'
bootstrap(engine)
with Session(engine) as db:
    db.add(UsuarioModel(username='Ana', password_hash=get_password_hash('right-pass'), role='produtor', is_admin=False, ativo=True))
    db.commit()
def rows(action=None):
    with engine.connect() as connection:
        query = 'SELECT action, request_count FROM auth_rate_limits'
        return connection.execute(text(query + (' WHERE action = :a' if action else '')), {'a': action}).all()
'''


class PersistentRateLimitTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_counters_window_and_hashed_keys(self):
        self.run_case(r'''
with Session(engine) as db:
    for _ in range(5):
        assert limits.hit(db, 'budget', '203.0.113.7', 5, 600) == (True, 0)
    allowed, retry = limits.hit(db, 'budget', '203.0.113.7', 5, 600)
    assert allowed is False and 590 <= retry <= 600
    assert limits.hit(db, 'budget', '203.0.113.8', 5, 600) == (True, 0)
    assert limits.blocked(db, 'budget', '203.0.113.7', 5)[0] is True
    # Keys are hashes; the address never reaches the table.
    with engine.connect() as connection:
        stored = connection.execute(text('SELECT key_hash FROM auth_rate_limits')).scalars().all()
    assert all(len(value) == 64 and '203.0.113' not in value for value in stored)
    # An expired window starts over.
    db.execute(text('UPDATE auth_rate_limits SET expires_at = :past, window_started_at = :older'),
               {'past': datetime.now(timezone.utc) - timedelta(seconds=1), 'older': datetime.now(timezone.utc) - timedelta(seconds=700)})
    db.commit()
    assert limits.blocked(db, 'budget', '203.0.113.7', 5) == (False, 0)
    assert limits.hit(db, 'budget', '203.0.113.7', 5, 600) == (True, 0)
    try: limits.hit(db, 'unknown', 'x', 1, 60)
    except ValueError: pass
    else: raise AssertionError('unknown action accepted')
''')

    def test_middleware_uses_the_database_and_falls_back_locally(self):
        self.run_case(r'''
os.environ['RATE_LIMIT_BACKEND'] = 'database'
assert limits.backend() == 'database'
for _ in range(5):
    assert limits.allow_shared('newsletter', '198.51.100.1', 5, 600)[0] is True
assert limits.allow_shared('newsletter', '198.51.100.1', 5, 600)[0] is False
assert rows('newsletter') == [('newsletter', 6)]
with patch.object(limits, 'hit', side_effect=OperationalError('select', {}, Exception('down'))):
    assert limits.allow_shared('newsletter', '198.51.100.2', 5, 600) == (True, 0)
assert rows('newsletter') == [('newsletter', 6)]
os.environ['RATE_LIMIT_BACKEND'] = 'local'
assert limits.allow_shared('budget', '198.51.100.3', 5, 600) == (True, 0)
assert rows('budget') == []
del os.environ['RATE_LIMIT_BACKEND']
assert limits.backend() == 'local'
''')

    def test_failed_logins_are_limited_per_account(self):
        self.run_case(r'''
app = FastAPI()
app.include_router(auth_router)
def session():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = session
async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        assert (await client.post('/auth/login', json={'username': 'Ana', 'password': 'right-pass'})).status_code == 200
        assert rows('login_account') == []
        for _ in range(10):
            assert (await client.post('/auth/login', json={'username': 'ana', 'password': 'wrong-pass'})).status_code == 401
        blocked = await client.post('/auth/login', json={'username': 'Ana', 'password': 'right-pass'})
        assert blocked.status_code == 429 and int(blocked.headers['retry-after']) > 0
        assert 'Muitas tentativas' in blocked.json()['detail']
        # Unknown logins are counted the same way, so the lock does not reveal accounts.
        for _ in range(10):
            assert (await client.post('/auth/login', json={'username': 'ninguem', 'password': 'wrong-pass'})).status_code == 401
        assert (await client.post('/auth/login', json={'username': 'ninguem', 'password': 'wrong-pass'})).status_code == 429
    with Session(engine) as db:
        db.execute(text("UPDATE auth_rate_limits SET expires_at = :past, window_started_at = :older"),
                   {'past': datetime.now(timezone.utc) - timedelta(seconds=1), 'older': datetime.now(timezone.utc) - timedelta(seconds=1000)})
        db.commit()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        assert (await client.post('/auth/login', json={'username': 'Ana', 'password': 'right-pass'})).status_code == 200
asyncio.run(check())
''')


if __name__ == "__main__":
    unittest.main()
