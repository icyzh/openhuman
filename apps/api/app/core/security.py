import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings


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
