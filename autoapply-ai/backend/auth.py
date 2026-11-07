import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

load_dotenv()

SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
ITERATIONS = 200_000
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), ITERATIONS)
    return hmac.compare_digest(digest.hex(), digest_hex)


def create_token(email: str) -> str:
    payload = {"sub": email, "exp": datetime.now(timezone.utc) + timedelta(days=7)}
    return jwt.encode(payload, SECRET, algorithm="HS256")


def current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer)) -> str:
    if creds is None:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(creds.credentials, SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Session expired. Sign in again.")
    return payload["sub"]
