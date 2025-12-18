# app/core/security.py
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union

import jwt  # Switch to PyJWT
from passlib.context import CryptContext
from app.core.config import settings

# 1. Configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"

# 2. Advanced Password Handling
def _pre_hash_password(password: str) -> str:
    """
    Handle the 'bcrypt 72-byte limit' safely.
    If a password is longer than 72 bytes, we hash it first using SHA-256.
    This ensures the entire password matters, regardless of length.
    """
    # Check byte length
    if len(password.encode('utf-8')) <= 72:
        return password
    
    # If too long, SHA-256 hash it and use the hexdigest as the input for bcrypt
    # SHA-256 hexdigest is 64 chars, which fits safely inside 72 bytes.
    hashed = hashlib.sha256(password.encode('utf-8')).hexdigest()
    return hashed

def hash_password(password: str) -> str:
    safe_password = _pre_hash_password(password)
    return pwd_context.hash(safe_password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    safe_password = _pre_hash_password(plain_password)
    return pwd_context.verify(safe_password, hashed_password)

# 3. Robust Token Creation
# app/core/security.py

def create_access_token(
    subject: Union[str, Any], 
    expires_delta: Optional[timedelta] = None,
    data: Optional[dict] = None
) -> str:
    
    # Use timezone-aware UTC
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "id": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "nbf": datetime.now(timezone.utc)
    }
    
    # Update with the dictionary passed in 'data'
    if data:
        to_encode.update(data)

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
# 4. Safer Decoding
def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[ALGORITHM],
            options={"verify_exp": True} # Explicitly confirm we want expiration checked
        )
        return payload
    except jwt.ExpiredSignatureError:
        # It is often helpful to catch this specifically for the caller
        raise
    except jwt.InvalidTokenError:
        raise