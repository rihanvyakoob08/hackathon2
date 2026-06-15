from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Dict

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _bcrypt_safe_password(password: str) -> bytes:
    return sha256(password.encode("utf-8")).hexdigest().encode("utf-8")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_bcrypt_safe_password(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    hashed_bytes = hashed_password.encode("utf-8")

    if bcrypt.checkpw(_bcrypt_safe_password(plain_password), hashed_bytes):
        return True

    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_bytes)
    except ValueError:
        return False


def create_access_token(data: Dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError as exc:
        raise credentials_exception from exc

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


async def get_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


async def get_officer(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in {"officer", "admin"}:
        raise HTTPException(status_code=403, detail="Officer access required")
    return current_user
