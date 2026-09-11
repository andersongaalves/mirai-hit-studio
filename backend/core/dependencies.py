import logging

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
from jose import jwt, JWTError

from core.config import settings

security = HTTPBearer()
logger = logging.getLogger(__name__)


def get_current_user(token=Depends(security)):

    try:
        payload = jwt.decode(
            token.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )

        return payload.get("sub")

    except JWTError:
        logger.warning("authentication_failed")

        raise HTTPException(status_code=401, detail="Token inválido")
