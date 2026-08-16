"""Cifratura simmetrica leggera per i token WhatsApp salvati in DB (access_token_encrypted)."""
import base64
import hashlib

from cryptography.fernet import Fernet

from app.config import SESSION_SECRET_KEY


def _fernet() -> Fernet:
    # Deriva una chiave Fernet valida (32 byte urlsafe-base64) dal secret esistente,
    # cosi' non serve gestire un'altra variabile d'ambiente separata per l'MVP.
    key = hashlib.sha256(SESSION_SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_token(plain: str) -> str:
    return _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_token(token: str) -> str:
    return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
