from pydantic import BaseModel
from datetime import datetime


class LoginRequest(BaseModel):
    username: str
    password: str


class UsuarioResponse(BaseModel):

    id: int
    username: str
    role: str
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}
