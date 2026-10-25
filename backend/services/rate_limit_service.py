"""AUD6-S12-003: request limits shared by every instance and kept across deploys.

Counters live in ``auth_rate_limits`` (keys are SHA-256 hashes, never raw IPs or
logins). The process-local SQLite limiter remains as a fallback when the
database is unreachable and as the default for SQLite test harnesses.
"""
import hashlib
import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

ACTIONS = ("login", "login_account", "budget", "newsletter", "checkout_payment", "checkout_resume")
_UPSERT = text("""
    INSERT INTO auth_rate_limits (
        key_hash, action, window_started_at, request_count, expires_at, created_at, updated_at
    ) VALUES (
        :key_hash, :action, :now, 1, :expires_at, :now, :now
    )
    ON CONFLICT (key_hash) DO UPDATE SET
        request_count = CASE
            WHEN auth_rate_limits.expires_at <= :now THEN 1
            ELSE auth_rate_limits.request_count + 1
        END,
        window_started_at = CASE
            WHEN auth_rate_limits.expires_at <= :now THEN :now
            ELSE auth_rate_limits.window_started_at
        END,
        expires_at = CASE
            WHEN auth_rate_limits.expires_at <= :now THEN :expires_at
            ELSE auth_rate_limits.expires_at
        END,
        updated_at = :now
    RETURNING request_count, expires_at
""")
_PEEK = text("SELECT request_count, expires_at FROM auth_rate_limits WHERE key_hash = :key_hash")
_PRUNE = text("DELETE FROM auth_rate_limits WHERE expires_at < :cutoff AND action IN ('login', 'login_account', 'budget', 'newsletter', 'checkout_payment', 'checkout_resume')")


def _now():
    return datetime.now(timezone.utc)


def _aware(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def key_hash(action, identity):
    return hashlib.sha256(f"rate-limit:{action}:{identity}".encode("utf-8")).hexdigest()


def backend():
    """``database`` on PostgreSQL unless RATE_LIMIT_BACKEND says otherwise."""
    configured = os.environ.get("RATE_LIMIT_BACKEND", "").strip().lower()
    if configured in ("database", "local"):
        return configured
    from database import engine

    return "database" if engine.dialect.name == "postgresql" else "local"


def hit(db, action, identity, limit, window_seconds):
    """Count one request; returns (allowed, retry_after_seconds). Commits."""
    if action not in ACTIONS:
        raise ValueError("unknown_rate_limit_action")
    now = _now()
    row = db.execute(_UPSERT, {
        "key_hash": key_hash(action, identity),
        "action": action,
        "now": now,
        "expires_at": now + timedelta(seconds=window_seconds),
    }).one()
    # Keep the table small without a scheduler: prune old counters now and then.
    if int.from_bytes(os.urandom(1), "big") < 3:
        db.execute(_PRUNE, {"cutoff": now - timedelta(days=1)})
    db.commit()
    count, expires_at = row
    if count > limit:
        return False, max(1, int((_aware(expires_at) - now).total_seconds()))
    return True, 0


def blocked(db, action, identity, limit):
    """True (with retry seconds) when the counter already reached ``limit``."""
    row = db.execute(_PEEK, {"key_hash": key_hash(action, identity)}).first()
    if row is None:
        return False, 0
    count, expires_at = row
    remaining = (_aware(expires_at) - _now()).total_seconds()
    if count >= limit and remaining > 0:
        return True, max(1, int(remaining))
    return False, 0


def allow_shared(action, identity, limit, window_seconds):
    """Middleware entry point: database counters with a local fallback."""
    from core.rate_limit import allow_request

    if backend() == "database":
        from database import SessionLocal

        db = SessionLocal()
        try:
            return hit(db, action, identity, limit, window_seconds)
        except SQLAlchemyError:
            db.rollback()
            logger.warning("rate_limit_database_unavailable action=%s", action)
        finally:
            db.close()
    return allow_request(f"{action}:{identity}", limit, window_seconds)
