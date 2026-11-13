import datetime
from typing import Any, Dict, Optional, Union
import bcrypt
from jose import jwt, JWTError
from app.core.config import settings

def get_password_hash(password: str) -> str:
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False

def create_access_token(
    subject: Union[str, Any],
    role: str,
    user_id: int,
    expires_delta: Optional[datetime.timedelta] = None
) -> str:
    """Create JWT access token."""
    if expires_delta:
        expire = datetime.datetime.now(datetime.timezone.utc) + expires_delta
    else:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode: Dict[str, Any] = {
        "exp": expire,
        "sub": str(subject),
        "role": role,
        "user_id": user_id,
        "type": "access"
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_verification_token(email: str, token_type: str = "email_verify") -> str:
    """Create temporary token for email verification or password reset."""
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)
    to_encode = {
        "exp": expire,
        "sub": email,
        "type": token_type
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None
