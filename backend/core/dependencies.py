import logging

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
from jose import JWTError

from core.security import decode_token
from database import get_db
from crud.crud_usuario import buscar_por_username

security = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


def get_current_user(token=Depends(security), db=Depends(get_db)):

    try:
        payload = decode_token(token.credentials) if token else {}
        user = buscar_por_username(db, payload["sub"]) if payload else None
        if user is None or not user.ativo:
            raise JWTError()
        return user

    except JWTError:
        logger.warning("authentication_failed")

        raise HTTPException(status_code=401, detail="Sessao invalida.", headers={"WWW-Authenticate": "Bearer"}) from None


def require_admin(user=Depends(get_current_user)):
    # Both fields exist with privileged defaults: deny inconsistent legacy records.
    if (not getattr(user, "ativo", False)
            or not getattr(user, "is_admin", False)
            or getattr(user, "role", None) != "admin"):
        raise HTTPException(status_code=403, detail="Permissao administrativa necessaria.")
    return user


def require_producer(user=Depends(get_current_user)):
    if (not getattr(user, "ativo", False)
            or getattr(user, "role", None) != "produtor"
            or getattr(user, "is_admin", False)):
        raise HTTPException(status_code=403, detail="Permissao de produtor necessaria.")
    return user


def require_client(user=Depends(get_current_user)):
    if (
        not getattr(user, "ativo", False)
        or getattr(user, "role", None) != "cliente"
        or getattr(user, "is_admin", False)
        or getattr(user, "cliente_id", None) is None
    ):
        raise HTTPException(status_code=403, detail="Permissao de cliente necessaria.")
    return user


def require_ai_operator(user=Depends(get_current_user)):
    """Keep the cross-client AI inbox restricted to administrators."""
    return require_admin(user)
