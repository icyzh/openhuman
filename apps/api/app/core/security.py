import base64
import os
from datetime import UTC, datetime, timedelta

import bcrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from jose import jwt

from app.core.config import settings

# ---- Password hashing ----


def hash_password(plain: str) -> str:
    """Hash a password with bcrypt."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Check a password against its bcrypt hash."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ---- JWT ----

def create_access_token(user_id: str) -> str:
    """Create a signed JWT for the given user ID."""
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT. Returns the payload or raises JWTError."""
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


# ---- Bot token encryption (AES-256-GCM) ----

def _get_encryption_key() -> bytes:
    raw = settings.encryption_key
    if not raw:
        raise RuntimeError("encryption_key is not set; generate a 32-byte hex string")
    try:
        key = bytes.fromhex(raw)
    except ValueError as exc:
        raise RuntimeError("encryption_key must be a valid hex string") from exc
    if len(key) != 32:
        raise RuntimeError("encryption_key must be 32 bytes (64 hex characters)")
    return key


def encrypt_token(plaintext: str) -> str:
    """Encrypt a bot token. Returns a base64-encoded ciphertext (nonce || data)."""
    key = _get_encryption_key()
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode(), None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode()


def decrypt_token(encoded: str) -> str:
    """Decrypt a bot token previously encrypted with encrypt_token()."""
    key = _get_encryption_key()
    raw = base64.urlsafe_b64decode(encoded)
    nonce, ciphertext = raw[:12], raw[12:]
    return AESGCM(key).decrypt(nonce, ciphertext, None).decode()
