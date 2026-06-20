import json
import os

from database import SessionLocal
from models.config import ConfigModel
from models.servico import ServicoModel
from models.projeto import ProjetoModel


def startup_database():

    db = SessionLocal()

    try:

        # Configuração global

        if not db.query(ConfigModel).first():

            db.add(ConfigModel(id=1))

        # Serviços

        if os.path.exists("backups/servicos_backup.json"):

            with open(
                "backups/servicos_backup.json",
                encoding="utf-8"
            ) as file:

                servicos = json.load(file)

            for item in servicos:

                existe = (
                    db.query(ServicoModel)
                    .filter(ServicoModel.nome == item["nome"])
                    .first()
                )

                if not existe:

                    db.add(ServicoModel(**item))

        # Projetos

        if os.path.exists("backups/projetos_backup.json"):

            with open(
                "backups/projetos_backup.json",
                encoding="utf-8"
            ) as file:

                projetos = json.load(file)

            for item in projetos:

                item.setdefault("destaque", False)

                existe = (
                    db.query(ProjetoModel)
                    .filter(ProjetoModel.titulo == item["titulo"])
                    .first()
                )

                if not existe:

                    db.add(ProjetoModel(**item))

        db.commit()

    finally:

        db.close()