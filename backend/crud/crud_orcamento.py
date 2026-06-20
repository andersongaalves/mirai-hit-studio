def criar(db, orcamento):

    novo = OrcamentoModel(
        **orcamento.model_dump()
    )

    db.add(novo)

    db.commit()

    db.refresh(novo)

    return novo


def listar(db):

    return (
        db.query(OrcamentoModel)
        .order_by(
            OrcamentoModel.id.desc()
        )
        .all()
    )

