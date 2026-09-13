import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import argparse
from getpass import getpass
from schemas.usuario import LoginRequest
from sqlalchemy.exc import SQLAlchemyError

from database import SessionLocal
from models.usuario import UsuarioModel
from core.security import get_password_hash

class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "Argumentos invalidos. Use --username; a senha sera solicitada interativamente.\n")


parser = SafeParser()

parser.add_argument("--username", required=True)


args = parser.parse_args()
if not sys.stdin.isatty():
    raise SystemExit("Execute em um terminal interativo.")
password = getpass("Senha: ")
if password != getpass("Confirme a senha: "):
    raise SystemExit("Senhas diferentes.")
try:
    LoginRequest(username=args.username, password=password)
    if len(password) < 8:
        raise ValueError()
except ValueError:
    raise SystemExit("Usuario/senha fora dos limites permitidos.") from None


db = SessionLocal()

try:

    existe = (
        db.query(UsuarioModel).filter(UsuarioModel.username == args.username).first()
    )

    if existe:

        print("Usuário já existe.")

    else:

        admin = UsuarioModel(
            username=args.username,
            password_hash=get_password_hash(password),
            is_admin=True,
            role="admin",
        )

        db.add(admin)

        db.commit()

        print("Administrador criado com sucesso!")

except SQLAlchemyError:
    db.rollback()
    raise SystemExit("Nao foi possivel criar o administrador.") from None
finally:

    db.close()
