import argparse

from database import SessionLocal
from models.usuario import UsuarioModel
from core.security import get_password_hash


parser = argparse.ArgumentParser()

parser.add_argument("--username", required=True)

parser.add_argument("--password", required=True)

args = parser.parse_args()


db = SessionLocal()

try:

    existe = (
        db.query(UsuarioModel)
        .filter(
            UsuarioModel.username == args.username
        )
        .first()
    )

    if existe:

        print("Usuário já existe.")

    else:

        admin = UsuarioModel(

            username=args.username,

            password_hash=get_password_hash(args.password),

            is_admin=True

        )

        db.add(admin)

        db.commit()

        print("Administrador criado com sucesso!")

finally:

    db.close()