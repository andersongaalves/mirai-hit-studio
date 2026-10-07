from core.dependencies import get_current_user
from core.security import create_access_token, verify_password
from crud import crud_usuario
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from schemas.usuario import LoginRequest, LoginResponse, UsuarioResponse
from sqlalchemy.orm import Session

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.get("/me", response_model=UsuarioResponse)
def current_user(user=Depends(get_current_user)):
    return user


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):

    usuario = crud_usuario.buscar_por_username(db, data.username)

    if usuario is None or not usuario.ativo or not verify_password(data.password, usuario.password_hash):

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos",
        )

    access_token = create_access_token({"sub": usuario.username, "av": usuario.auth_version})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UsuarioResponse.model_validate(usuario),
    }
