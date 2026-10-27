from core.security import get_password_hash
from crud import crud_usuario
from models.cliente import ClienteModel
from models.projeto_credito import ProjetoCreditoModel
from models.usuario import UsuarioModel
from schemas.usuario import UsuarioCreate, UsuarioPasswordUpdate, UsuarioUpdate, especialidades_lista
from services import audit_service
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


class UsuarioNaoEncontrado(Exception):
    pass


class UsuarioConflito(Exception):
    pass


class UsuarioInvalido(Exception):
    pass


def _validar_vinculo_cliente(
    db: Session,
    *,
    role: str,
    cliente_id: int | None,
    usuario_id: int | None = None,
):
    if role != "cliente":
        if cliente_id is not None:
            raise UsuarioInvalido(
                "Somente usuarios clientes podem possuir cliente vinculado."
            )
        return
    if cliente_id is None:
        raise UsuarioInvalido("Usuario cliente exige um cliente vinculado.")
    if db.get(ClienteModel, cliente_id) is None:
        raise UsuarioInvalido("Cliente vinculado nao encontrado.")
    if crud_usuario.cliente_em_uso(db, cliente_id, usuario_id):
        raise UsuarioConflito("Cliente ja possui uma conta vinculada.")


def _validar_email(db: Session, *, role: str, email: str | None, usuario_id: int | None = None):
    # AUD6-S02-004: one e-mail recovers exactly one account.
    if not email:
        return
    if role == "cliente":
        raise UsuarioInvalido("Contas de cliente usam o e-mail do cadastro do cliente.")
    from models.cliente import ClienteModel
    from sqlalchemy import func

    other = db.query(UsuarioModel.id).filter(func.lower(UsuarioModel.email) == email.lower())
    if usuario_id is not None:
        other = other.filter(UsuarioModel.id != usuario_id)
    if other.first() is not None:
        raise UsuarioConflito("Este e-mail já está em outra conta.")
    if db.query(ClienteModel.id).filter(func.lower(ClienteModel.email) == email.lower()).first() is not None:
        raise UsuarioConflito("Este e-mail pertence a um cliente; use outro para a conta interna.")


def _perfil_produtor(role: str, especialidades, cpf):
    """Specialties belong to producers; the CPF is asked only of beatmakers."""
    if role != "produtor":
        return None, None
    especialidades = list(especialidades or [])
    if "beatmaker" not in especialidades:
        cpf = None
    elif not cpf:
        raise UsuarioInvalido("Informe o CPF do beatmaker (usado nos contratos de beat).")
    return ",".join(especialidades) or None, cpf


def _buscar(db: Session, usuario_id: int):
    usuario = crud_usuario.buscar_por_id(db, usuario_id)
    if not usuario:
        raise UsuarioNaoEncontrado("Usuario nao encontrado.")
    return usuario


def listar(db: Session, busca: str = "", ativo: bool | None = None, role: str | None = None):
    return crud_usuario.listar_usuarios(db, busca, ativo, role)


def buscar(db: Session, usuario_id: int):
    return _buscar(db, usuario_id)


def criar(db: Session, dados: UsuarioCreate, ator, request_id: str | None = None):
    payload = dados.model_dump()
    username = payload["username"]
    if crud_usuario.username_em_uso(db, username):
        raise UsuarioConflito("Nome de usuario ja cadastrado.")
    role = payload.pop("role")
    password = payload.pop("password")
    _validar_vinculo_cliente(db, role=role, cliente_id=payload.get("cliente_id"))
    _validar_email(db, role=role, email=payload.get("email"))
    payload["especialidades"], payload["cpf"] = _perfil_produtor(
        role, payload.get("especialidades"), payload.get("cpf"))
    try:
        usuario = crud_usuario.criar_sem_commit(db, {
            **payload,
            "password_hash": get_password_hash(password),
            "role": role,
            "is_admin": role == "admin",
            "ativo": True,
        })
        audit_service.record(
            db,
            actor=ator,
            action="user.created",
            entity_type="user",
            entity_id=usuario.id,
            metadata={"new_role": role, "new_active": True},
            request_id=request_id,
        )
        db.commit()
        db.refresh(usuario)
        return usuario
    except IntegrityError:
        db.rollback()
        raise UsuarioConflito(
            "Nome de usuario ou cliente vinculado ja cadastrado."
        ) from None
    except Exception:
        db.rollback()
        raise


def atualizar(db: Session, usuario_id: int, dados: UsuarioUpdate, ator, request_id: str | None = None):
    usuario = _buscar(db, usuario_id)
    old_role = usuario.role
    old_active = usuario.ativo
    old_display = usuario.nome_exibicao
    old_username = usuario.username
    old_profile = (usuario.especialidades, usuario.cpf)
    payload = dados.model_dump(exclude_unset=True)
    if "username" in payload and crud_usuario.username_em_uso(db, payload["username"], usuario.id):
        raise UsuarioConflito("Nome de usuario ja cadastrado.")
    if usuario.id == ator.id and payload.get("username", usuario.username) != usuario.username:
        raise UsuarioConflito("Nao e permitido alterar o proprio nome de usuario.")

    proximo_role = payload.get("role", usuario.role)
    proximo_painel_beats = payload.get("painel_beats", usuario.painel_beats)
    if proximo_painel_beats and proximo_role != "produtor":
        raise UsuarioInvalido("Painel de beats permitido apenas para produtores.")
    if proximo_role != "produtor":
        payload["painel_beats"] = False
    if {"especialidades", "cpf", "role"} & payload.keys():
        payload["especialidades"], payload["cpf"] = _perfil_produtor(
            proximo_role,
            payload["especialidades"] if payload.get("especialidades") is not None
            else especialidades_lista(usuario.especialidades),
            payload["cpf"] if "cpf" in payload else usuario.cpf,
        )
    if usuario.is_test and (proximo_role == "admin" or payload.get("username", usuario.username).strip().lower() == "yonda"):
        raise UsuarioConflito("Conta de teste exige reversao validada antes de assumir identidade protegida.")
    proximo_ativo = payload.get("ativo", usuario.ativo)
    if "role" in payload and proximo_role != "cliente":
        payload["cliente_id"] = None
    proximo_cliente_id = payload.get("cliente_id", usuario.cliente_id)
    if proximo_role == "cliente":
        payload["email"] = None  # clients keep their e-mail in the client record
    if "email" in payload and payload["email"] != usuario.email:
        # A new address invalidates any pending recovery link.
        payload["reset_token_hash"] = None
        payload["reset_expires_at"] = None
    _validar_email(db, role=proximo_role, email=payload.get("email", usuario.email), usuario_id=usuario.id)
    _validar_vinculo_cliente(
        db,
        role=proximo_role,
        cliente_id=proximo_cliente_id,
        usuario_id=usuario.id,
    )
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
        # AUD6-S02-001/002: renaming, deactivating or changing the role ends every open
        # session. Tokens carry the username, so a renamed login could otherwise be
        # reused by a new account, and a reactivated account would revive old tokens.
        if usuario.username != old_username or (old_active and not usuario.ativo) or usuario.role != old_role:
            usuario.auth_version += 1
            db.flush()
        if usuario.nome_exibicao != old_display or usuario.username != old_username:
            # Keeps the credited fallback name current (used if the account is ever removed).
            db.query(ProjetoCreditoModel).filter(ProjetoCreditoModel.usuario_id == usuario.id).update(
                {ProjetoCreditoModel.nome: usuario.nome_exibicao or usuario.username}, synchronize_session=False)
        action = "user.updated"
        if old_active and not usuario.ativo:
            action = "user.deactivated"
        elif not old_active and usuario.ativo:
            action = "user.reactivated"
        audit_service.record(
            db,
            actor=ator,
            action=action,
            entity_type="user",
            entity_id=usuario.id,
            metadata={
                "old_role": old_role,
                "new_role": usuario.role,
                "old_active": old_active,
                "new_active": usuario.ativo,
                # Names of the changed fields only; never the CPF itself.
                **({"changed_keys": ",".join(changed)} if (changed := [
                    key for key, changed_value in (
                        ("nome_exibicao", usuario.nome_exibicao != old_display),
                        ("especialidades", usuario.especialidades != old_profile[0]),
                        ("cpf", usuario.cpf != old_profile[1]),
                    ) if changed_value
                ]) else {}),
            },
            request_id=request_id,
        )
        db.commit()
        db.refresh(usuario)
        return usuario
    except IntegrityError:
        db.rollback()
        raise UsuarioConflito(
            "Nome de usuario ou cliente vinculado ja cadastrado."
        ) from None
    except Exception:
        db.rollback()
        raise


def redefinir_senha(
    db: Session,
    usuario_id: int,
    dados: UsuarioPasswordUpdate,
    ator,
    request_id: str | None = None,
):
    try:
        usuario = db.scalar(
            select(UsuarioModel)
            .where(UsuarioModel.id == usuario_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if usuario is None:
            raise UsuarioNaoEncontrado("Usuario nao encontrado.")
        usuario.password_hash = get_password_hash(dados.nova_senha)
        usuario.auth_version += 1
        audit_service.record(
            db,
            actor=ator,
            action="user.password_reset",
            entity_type="user",
            entity_id=usuario.id,
            request_id=request_id,
        )
        db.commit()
        db.refresh(usuario)
        return usuario
    except Exception:
        db.rollback()
        raise
