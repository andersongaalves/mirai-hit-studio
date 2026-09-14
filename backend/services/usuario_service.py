from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.security import get_password_hash
from crud import crud_usuario
from schemas.usuario import UsuarioCreate, UsuarioPasswordUpdate, UsuarioUpdate


class UsuarioNaoEncontrado(Exception):
    pass


class UsuarioConflito(Exception):
    pass


def _buscar(db: Session, usuario_id: int):
    usuario = crud_usuario.buscar_por_id(db, usuario_id)
    if not usuario:
        raise UsuarioNaoEncontrado("Usuario nao encontrado.")
    return usuario


def listar(db: Session, busca: str = "", ativo: bool | None = None, role: str | None = None):
    return crud_usuario.listar_usuarios(db, busca, ativo, role)


def buscar(db: Session, usuario_id: int):
    return _buscar(db, usuario_id)


def criar(db: Session, dados: UsuarioCreate):
    payload = dados.model_dump()
    username = payload["username"]
    if crud_usuario.username_em_uso(db, username):
        raise UsuarioConflito("Nome de usuario ja cadastrado.")
    role = payload.pop("role")
    password = payload.pop("password")
    try:
        usuario = crud_usuario.criar_sem_commit(db, {
            **payload,
            "password_hash": get_password_hash(password),
            "role": role,
            "is_admin": role == "admin",
            "ativo": True,
        })
        db.commit()
        db.refresh(usuario)
        return usuario
    except IntegrityError:
        db.rollback()
        raise UsuarioConflito("Nome de usuario ja cadastrado.") from None
    except Exception:
        db.rollback()
        raise


def atualizar(db: Session, usuario_id: int, dados: UsuarioUpdate, ator):
    usuario = _buscar(db, usuario_id)
    payload = dados.model_dump(exclude_unset=True)
    if "username" in payload and crud_usuario.username_em_uso(db, payload["username"], usuario.id):
        raise UsuarioConflito("Nome de usuario ja cadastrado.")
    if usuario.id == ator.id and payload.get("username", usuario.username) != usuario.username:
        raise UsuarioConflito("Nao e permitido alterar o proprio nome de usuario.")

    proximo_role = payload.get("role", usuario.role)
    proximo_ativo = payload.get("ativo", usuario.ativo)
    perde_admin = usuario.role == "admin" and usuario.is_admin and (
        proximo_role != "admin" or not proximo_ativo
    )
    if usuario.id == ator.id and (proximo_role != "admin" or not proximo_ativo):
        raise UsuarioConflito("Nao e permitido remover o proprio acesso administrativo.")
    if perde_admin and len(crud_usuario.bloquear_admins_ativos(db)) <= 1:
        raise UsuarioConflito("O ultimo administrador ativo nao pode ser desativado.")
    if "role" in payload:
        payload["is_admin"] = proximo_role == "admin"
    try:
        crud_usuario.atualizar_sem_commit(db, usuario, payload)
        db.commit()
        db.refresh(usuario)
        return usuario
    except IntegrityError:
        db.rollback()
        raise UsuarioConflito("Nome de usuario ja cadastrado.") from None
    except Exception:
        db.rollback()
        raise


def redefinir_senha(db: Session, usuario_id: int, dados: UsuarioPasswordUpdate):
    usuario = _buscar(db, usuario_id)
    try:
        usuario.password_hash = get_password_hash(dados.nova_senha)
        db.commit()
        db.refresh(usuario)
        return usuario
    except Exception:
        db.rollback()
        raise
