from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr
)

class NewsletterCreate(BaseModel):
    email: EmailStr

class NewsletterResponse(BaseModel):

    id: int
    email: EmailStr
    ativo: bool
    origem: str
    data_cadastro: datetime
    model_config = ConfigDict(
        from_attributes=True
    )