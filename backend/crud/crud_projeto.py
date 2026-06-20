def listar(db):

    return db.query(
        ProjetoModel
    ).all()


def criar(db, projeto):

    novo = ProjetoModel(
        **projeto.model_dump()
    )

    db.add(novo)

    db.commit()

    db.refresh(novo)

    return novo


def atualizar(
    db,
    projeto_id,
    dados
):

    projeto = (
        db.query(ProjetoModel)
        .filter(
            ProjetoModel.id == projeto_id
        )
        .first()
    )

    if not projeto:

        return None

    for campo, valor in dados.model_dump().items():

        setattr(projeto, campo, valor)

    db.commit()

    db.refresh(projeto)

    return projeto


def deletar(
    db,
    projeto_id
):

    projeto = (
        db.query(ProjetoModel)
        .filter(
            ProjetoModel.id == projeto_id
        )
        .first()
    )

    if not projeto:

        return False

    db.delete(projeto)

    db.commit()

    return True