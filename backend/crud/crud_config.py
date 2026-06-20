def get_config(db):

    return (
        db.query(ConfigModel)
        .filter(ConfigModel.id == 1)
        .first()
    )


def update_config(db, novo_config):

    config = (
        db.query(ConfigModel)
        .filter(ConfigModel.id == 1)
        .first()
    )

    for key, value in novo_config.model_dump().items():

        setattr(config, key, value)

    db.commit()

    db.refresh(config)

    return config