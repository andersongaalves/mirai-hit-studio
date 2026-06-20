from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from crud import crud_usuario
from schemas.usuario import LoginRequest
from core.security import (verify_password, create_access_token)

router = APIRouter(
    prefix="/auth",
    tags=["Autenticação"]
)


@router.post("/login")
def login(
    data: LoginRequest,
    db: Session = Depends(get_db)

):

    usuario = crud_usuario.buscar_por_username(
        db,
        data.username
    )

    if (
        usuario is None
        or
        not verify_password(
            data.password,
            usuario.password_hash
        )
    ):

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos"
        )

    access_token = create_access_token(
        {
            "sub": usuario.username
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }