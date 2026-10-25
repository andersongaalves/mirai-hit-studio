from core.dependencies import get_current_user
from core.security import create_access_token, get_password_hash, verify_password
from crud import crud_usuario
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from schemas.usuario import LoginRequest, LoginResponse, SessaoUsuarioResponse
from sqlalchemy.orm import Session

router = APIRouter(prefix="/auth", tags=["Autenticação"])


_DUMMY_HASH = None


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

    usuario = crud_usuario.buscar_por_username(db, data.username)
    password_ok = verify_password(
        data.password,
        usuario.password_hash if usuario is not None else _dummy_hash(),
    )

    if usuario is None or not usuario.ativo or not password_ok:

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
