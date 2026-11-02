"""Admin file manager: browse, download, inspect and delete stored files."""
from typing import Annotated, Literal
from urllib.parse import quote

from core.dependencies import require_admin
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from services import arquivos_admin_service as service
from services import producao_arquivo_service
from sqlalchemy.orm import Session

router = APIRouter(prefix="/admin/arquivos", tags=["Arquivos (Admin)"])
Db = Annotated[Session, Depends(get_db)]
Admin = Annotated[object, Depends(require_admin)]


class Exclusao(BaseModel):
    model_config = ConfigDict(extra="forbid")

    motivo: str = Field(min_length=3, max_length=300)


@router.get("")
def listar(db: Db, user: Admin,
           pasta: Annotated[str | None, Query(max_length=300)] = None,
           categoria: Literal["audio", "pdf", "imagem", "compactado", "outro"] | None = None,
           funcao: Annotated[str | None, Query(max_length=60)] = None,
           servico: Annotated[str | None, Query(max_length=60)] = None,
           protegido: bool | None = None,
           busca: Annotated[str | None, Query(max_length=120)] = None,
           ordem: Literal["recentes", "antigos", "maiores", "nome"] = "recentes"):
    return service.listar(db, pasta=pasta, categoria_filtro=categoria, funcao=funcao, servico=servico,
                          protegido=protegido, busca=busca, ordem=ordem)


@router.get("/conteudo")
def baixar(ref: Annotated[str, Query(min_length=3, max_length=80)], db: Db, user: Admin):
    result = service.conteudo(db, ref)
    if isinstance(result, dict):
        return result
    data, filename, mime = result
    return Response(content=data, media_type=mime or "application/octet-stream", headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
        "Cache-Control": "private, no-store",
    })


@router.delete("", status_code=204)
def excluir(ref: Annotated[str, Query(min_length=3, max_length=80)], dados: Exclusao, request: Request, db: Db,
            user: Admin):
    try:
        service.excluir(db, ref, user, dados.motivo, request_id=getattr(request.state, "request_id", None))
    except producao_arquivo_service.ProducaoArquivoError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from None
    return Response(status_code=204)
