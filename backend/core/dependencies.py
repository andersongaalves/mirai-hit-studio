from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
from jose import jwt, JWTError

from core.config import settings

security = HTTPBearer()


def get_current_user(token=Depends(security)):

    print("================================")
    print("TOKEN RECEBIDO:", token.credentials)

    try:
        payload = jwt.decode(
            token.credentials,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        print("PAYLOAD:", payload)

        return payload.get("sub")

    except JWTError as e:

        print("ERRO JWT:", repr(e))
        print("SECRET:", settings.SECRET_KEY)
        print("ALGORITHM:", settings.ALGORITHM)

        raise HTTPException(
            status_code=401,
            detail="Token inválido"
        )