from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from core.dependencies import get_current_user, require_admin
from schemas.usuario import UsuarioCreate, UsuarioPasswordUpdate, UsuarioResponse, UsuarioUpdate
from services import usuario_service

router = APIRouter(prefix="/usuarios", tags=["Usuários"])


def _erro(error):
    if isinstance(error, usuario_service.UsuarioNaoEncontrado):
        raise HTTPException(status_code=404, detail=str(error)) from None
    if isinstance(error, usuario_service.UsuarioConflito):
        raise HTTPException(status_code=409, detail=str(error)) from None
    raise error


@router.get("", response_model=list[UsuarioResponse])
def listar_usuarios(
    busca: str = Query(default="", max_length=50),
    ativo: bool | None = None,
    role: str | None = Query(default=None, pattern="^(admin|produtor)$"),
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    return usuario_service.listar(db, busca.strip(), ativo, role)


@router.get("/produtores", response_model=list[UsuarioResponse])
def listar_produtores_ativos(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return usuario_service.listar(db, ativo=True)


@router.get("/{usuario_id}", response_model=UsuarioResponse)
def obter_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    try:
        return usuario_service.buscar(db, usuario_id)
    except Exception as error:
        _erro(error)


@router.post("", response_model=UsuarioResponse, status_code=201)
def criar_usuario(
    dados: UsuarioCreate,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    try:
        return usuario_service.criar(db, dados)
    except Exception as error:
        _erro(error)


@router.patch("/{usuario_id}", response_model=UsuarioResponse)
def atualizar_usuario(
    usuario_id: int,
    dados: UsuarioUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    try:
        return usuario_service.atualizar(db, usuario_id, dados, user)
    except Exception as error:
        _erro(error)


@router.patch("/{usuario_id}/senha", response_model=UsuarioResponse)
def redefinir_senha(
    usuario_id: int,
    dados: UsuarioPasswordUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    try:
        return usuario_service.redefinir_senha(db, usuario_id, dados)
    except Exception as error:
        _erro(error)
