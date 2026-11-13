import logging

from core.security import decode_token
from crud.crud_usuario import buscar_por_username
from database import get_db
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer
from jose import JWTError

security = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


# Admin preview sessions only read: anything else is refused before the route runs.
PREVIEW_METHODS = ("GET", "HEAD", "OPTIONS")
PREVIEW_READ_ONLY = "Modo de visualização do Admin: nada pode ser enviado ou alterado."
PREVIEW_ROLES = ("cliente", "produtor")


def _preview_admin(db, payload):
    """The admin who opened a preview session, still active and with the same sign-in."""
    from models import UsuarioModel

    admin_id, admin_version = payload.get("adm"), payload.get("aav")
    if type(admin_id) is not int or type(admin_version) is not int:
        return None
    admin = db.get(UsuarioModel, admin_id)
    if (admin is None or not admin.ativo or not admin.is_admin or admin.role != "admin"
            or admin.auth_version != admin_version):
        return None
    return admin


def get_current_user(request: Request, token=Depends(security), db=Depends(get_db)):

    try:
        payload = decode_token(token.credentials) if token else {}
        preview = None
        if not payload and token:
            payload = decode_token(token.credentials, "preview")
            preview = _preview_admin(db, payload) if payload else None
            if payload and preview is None:
                raise JWTError()
        user = buscar_por_username(db, payload["sub"]) if payload else None
        auth_version = payload.get("av")
        account_id = payload.get("uid")
        if (
            user is None
            # AUD6-S02-001: a token issued to a renamed account must never authenticate a
            # new account that later reused the same login. Tokens without "uid" were
            # issued before this check and expire within the access-token lifetime.
            or (account_id is not None and (type(account_id) is not int or account_id != user.id))
            or not user.ativo
            or type(auth_version) is not int
            or auth_version < 0
            or auth_version != user.auth_version
            or (preview is not None and (user.role not in PREVIEW_ROLES or user.is_admin or account_id is None))
        ):
            raise JWTError()
        if preview is not None:
            request.state.preview_admin_id = preview.id
            if request.method not in PREVIEW_METHODS:
                raise HTTPException(status_code=403, detail=PREVIEW_READ_ONLY)
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


def _is_client(user):
    return (getattr(user, "ativo", False)
            and getattr(user, "role", None) == "cliente"
            and not getattr(user, "is_admin", False)
            and getattr(user, "cliente_id", None) is not None)


def require_client(user=Depends(get_current_user)):
    """The studio client portal. Accounts created on the Labs store are not studio clients."""
    if not _is_client(user) or getattr(user, "somente_labs", False):
        raise HTTPException(status_code=403, detail="Permissao de cliente necessaria.")
    return user


def require_labs_customer(user=Depends(get_current_user)):
    """Mirai Hit Labs purchases and downloads: studio clients and Labs-only accounts."""
    if not _is_client(user):
        raise HTTPException(status_code=403, detail="Permissao de cliente necessaria.")
    return user


def require_ai_operator(user=Depends(get_current_user)):
    """Keep the cross-client AI inbox restricted to administrators."""
    return require_admin(user)
