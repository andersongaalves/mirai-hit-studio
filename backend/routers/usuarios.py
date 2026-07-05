from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from core.dependencies import get_current_user
from schemas.usuario import UsuarioResponse
from crud import crud_usuario

router = APIRouter(prefix="/usuarios", tags=["Usuários"])


@router.get("", response_model=list[UsuarioResponse])
def listar_usuarios(db: Session = Depends(get_db), user=Depends(get_current_user)):

    return crud_usuario.listar_usuarios(db)
