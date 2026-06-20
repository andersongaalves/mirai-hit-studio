from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from core.config import settings


ALGORITHM = "HS256"


# ===========================
# SENHAS
# ===========================

def get_password_hash(password: str) -> str:
    """
    Gera um hash seguro utilizando bcrypt.
    """

    salt = bcrypt.gensalt()

    password_hash = bcrypt.hashpw(
        password.encode("utf-8"),
        salt
    )

    return password_hash.decode("utf-8")


def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    """
    Verifica se a senha informada corresponde ao hash salvo.
    """

    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )


# ===========================
# JWT
# ===========================

def create_access_token(
    data: dict[str, Any]
) -> str:
    """
    Cria um Access Token JWT.
    """

    payload = data.copy()

    expire = datetime.now(
        timezone.utc
    ) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload.update(
        {
            "exp": expire,
            "type": "access"
        }
    )

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=ALGORITHM
    )


def create_refresh_token(
    data: dict[str, Any]
) -> str:
    """
    Cria um Refresh Token.
    """

    payload = data.copy()

    expire = datetime.now(
        timezone.utc
    ) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    payload.update(
        {
            "exp": expire,
            "type": "refresh"
        }
    )

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=ALGORITHM
    )


def decode_token(token: str) -> dict:
    """
    Decodifica um JWT válido.
    """

    try:

        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM]
        )

    except JWTError:

        return {}