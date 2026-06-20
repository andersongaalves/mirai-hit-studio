from sqlalchemy.orm import Session

from models.usuario import UsuarioModel


def buscar_por_username(
    db: Session,
    username: str
):

    return (

        db.query(UsuarioModel)

        .filter(
            UsuarioModel.username == username
        )

        .first()

    )