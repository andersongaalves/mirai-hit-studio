from sqlalchemy.orm import Session

from models.usuario import UsuarioModel


def buscar_por_username(db: Session, username: str):

    return db.query(UsuarioModel).filter(UsuarioModel.username == username).first()


def buscar_por_id(db: Session, usuario_id: int):
    return db.get(UsuarioModel, usuario_id)


def listar_usuarios(
    db: Session,
    busca: str = "",
    ativo: bool | None = None,
    role: str | None = None,
):
    query = db.query(UsuarioModel)
    if busca:
        query = query.filter(UsuarioModel.username.ilike(f"%{busca}%"))
    if ativo is not None:
        query = query.filter(UsuarioModel.ativo.is_(ativo))
    if role:
        query = query.filter(UsuarioModel.role == role)
    return query.order_by(UsuarioModel.username.asc()).all()


def username_em_uso(db: Session, username: str, ignorar_id: int | None = None):
    query = db.query(UsuarioModel).filter(UsuarioModel.username == username)
    if ignorar_id is not None:
        query = query.filter(UsuarioModel.id != ignorar_id)
    return query.first() is not None


def bloquear_admins_ativos(db: Session):
    return (
        db.query(UsuarioModel)
        .filter(
            UsuarioModel.ativo.is_(True),
            UsuarioModel.is_admin.is_(True),
            UsuarioModel.role == "admin",
        )
        .with_for_update()
        .all()
    )


def criar_sem_commit(db: Session, dados: dict):
    usuario = UsuarioModel(**dados)
    db.add(usuario)
    db.flush()
    return usuario


def atualizar_sem_commit(db: Session, usuario: UsuarioModel, dados: dict):
    for campo, valor in dados.items():
        setattr(usuario, campo, valor)
    db.flush()
    return usuario
