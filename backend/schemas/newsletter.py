from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class NewsletterCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr = Field(max_length=150)


class NewsletterResponse(BaseModel):

    id: int
    email: EmailStr
    ativo: bool
    origem: str
    data_cadastro: datetime
    model_config = ConfigDict(from_attributes=True)
