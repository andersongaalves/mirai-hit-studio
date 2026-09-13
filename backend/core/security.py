from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from core.config import settings

ALGORITHM = settings.ALGORITHM


# ===========================
# SENHAS
# ===========================


def get_password_hash(password: str) -> str:
    """
    Gera um hash seguro utilizando bcrypt.
    """

    if not password or len(password.encode("utf-8")) > 72:
        raise ValueError("Senha deve conter entre 1 e 72 bytes UTF-8.")
    salt = bcrypt.gensalt()

    password_hash = bcrypt.hashpw(password.encode("utf-8"), salt)

    return password_hash.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica se a senha informada corresponde ao hash salvo.
    """

    if not plain_password or len(plain_password.encode("utf-8")) > 72:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ===========================
# JWT
# ===========================


def create_access_token(data: dict[str, Any]) -> str:
    """
    Cria um Access Token JWT.
    """

    payload = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload.update({"exp": expire, "type": "access"})

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict[str, Any]) -> str:
    """
    Cria um Refresh Token.
    """

    payload = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    payload.update({"exp": expire, "type": "refresh"})

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str, token_type="access") -> dict:
    """
    Decodifica um JWT válido.
    """

    try:

        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM],
                             options={"require_exp": True, "require_sub": True})
        if not isinstance(payload.get("sub"), str) or not payload["sub"].strip() or payload.get("type") != token_type:
            return {}
        return payload

    except (JWTError, ValueError, TypeError, OverflowError):

        return {}
