from core.dependencies import get_current_user
from core.security import create_access_token, get_password_hash, verify_password
from crud import crud_usuario
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Response, status
from schemas.usuario import LoginRequest, LoginResponse, SenhaPropriaUpdate, SessaoUsuarioResponse
from services import rate_limit_service
from sqlalchemy.orm import Session

router = APIRouter(prefix="/auth", tags=["Autenticação"])


_DUMMY_HASH = None
# AUD6-S02-009: failed passwords are also counted per login, so spreading attempts
# over many addresses does not help. Unknown logins are counted the same way.
ACCOUNT_FAILURES = 10
ACCOUNT_WINDOW_SECONDS = 900
TOO_MANY = "Muitas tentativas. Aguarde alguns minutos e tente novamente."


def _dummy_hash():
    # AUD6-S02-008: an unknown login costs the same bcrypt check as a wrong password.
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = get_password_hash("mirai-login-timing-equalizer")
    return _DUMMY_HASH


@router.get("/me", response_model=SessaoUsuarioResponse, response_model_exclude_none=True)
def current_user(user=Depends(get_current_user)):
    return SessaoUsuarioResponse.from_user(user)


@router.post("/login", response_model=LoginResponse, response_model_exclude_none=True)
def login(data: LoginRequest, db: Session = Depends(get_db)):

    account_key = data.username.strip().lower()
    locked, retry = rate_limit_service.blocked(db, "login_account", account_key, ACCOUNT_FAILURES)
    if locked:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, TOO_MANY, headers={"Retry-After": str(retry)})

    usuario = crud_usuario.buscar_por_username(db, data.username)
    password_ok = verify_password(
        data.password,
        usuario.password_hash if usuario is not None else _dummy_hash(),
    )

    if usuario is None or not usuario.ativo or not password_ok:
        rate_limit_service.hit(db, "login_account", account_key, ACCOUNT_FAILURES, ACCOUNT_WINDOW_SECONDS)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos",
        )

    # "uid" binds the session to the account itself, not only to its (renamable) login.
    access_token = create_access_token({"sub": usuario.username, "av": usuario.auth_version, "uid": usuario.id})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": SessaoUsuarioResponse.from_user(usuario),
    }


PASSWORD_CHANGE_FAILURES = 5


@router.post("/senha", response_model=LoginResponse, response_model_exclude_none=True)
def trocar_senha(data: SenhaPropriaUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    # AUD6-S02-004: the current password proves it is the owner; every other session ends.
    from services import conta_interna_service

    key = f"password-change:{user.id}"
    locked, retry = rate_limit_service.blocked(db, "login_account", key, PASSWORD_CHANGE_FAILURES)
    if locked:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, TOO_MANY, headers={"Retry-After": str(retry)})
    try:
        updated = conta_interna_service.trocar_senha(db, user.id, data.senha_atual, data.nova_senha)
    except conta_interna_service.SenhaAtualIncorreta:
        rate_limit_service.hit(db, "login_account", key, PASSWORD_CHANGE_FAILURES, ACCOUNT_WINDOW_SECONDS)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Senha atual incorreta.") from None
    access_token = create_access_token({"sub": updated.username, "av": updated.auth_version, "uid": updated.id})
    return {"access_token": access_token, "token_type": "bearer", "user": SessaoUsuarioResponse.from_user(updated)}


@router.post("/sair-de-todos", status_code=status.HTTP_204_NO_CONTENT)
def sair_de_todos(db: Session = Depends(get_db), user=Depends(get_current_user)):
    # AUD6-S02-006: every token issued so far stops working, on every device.
    from services import conta_interna_service

    conta_interna_service.encerrar_sessoes(db, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
