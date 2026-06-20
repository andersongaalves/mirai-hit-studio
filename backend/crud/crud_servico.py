def listar(db):

    return db.query(
        ServicoModel
    ).all()


def criar(db, servico):

    novo = ServicoModel(
        **servico.model_dump()
    )

    db.add(novo)

    db.commit()

    db.refresh(novo)

    return novo


def atualizar(
    db,
    servico_id,
    dados
):

    servico = (
        db.query(ServicoModel)
        .filter(
            ServicoModel.id == servico_id
        )
        .first()
    )

    if not servico:

        return None

    for campo, valor in dados.model_dump().items():

        setattr(servico, campo, valor)

    db.commit()

    db.refresh(servico)

    return servico


def deletar(
    db,
    servico_id
):

    servico = (
        db.query(ServicoModel)
        .filter(
            ServicoModel.id == servico_id
        )
        .first()
    )

    if not servico:

        return False

    db.delete(servico)

    db.commit()

    return True