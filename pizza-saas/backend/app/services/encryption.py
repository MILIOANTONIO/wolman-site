"""
Cifratura a riposo per segreti nel database (token OAuth social di
Promoziona milestone 4+ - vedi SocialConnection in models.py). Nessun altra
tabella oggi tiene segreti in chiaro nel DB (le chiavi provider vivono solo
come variabili d'ambiente su Render), quindi questa e' la prima volta che
serve una colonna cifrata: Fernet (AES128-CBC + HMAC, libreria `cryptography`
gia' in requirements.txt), chiave in ENCRYPTION_KEY.

ENCRYPTION_KEY non e' ancora impostata su Render - generarla con
`Fernet.generate_key()` e aggiungerla come secret (mai in chat/git), stesso
schema seguito per DEEPL_API_KEY/KLING_API_KEY. Finche' manca, encrypt/decrypt
sollevano un errore chiaro invece di salvare/leggere segreti in chiaro.
"""
import os

from cryptography.fernet import Fernet, InvalidToken


class EncryptionNotConfigured(Exception):
    pass


def _get_fernet() -> Fernet:
    key = os.environ.get("ENCRYPTION_KEY")
    if not key:
        raise EncryptionNotConfigured(
            "ENCRYPTION_KEY non configurata - genera una chiave con Fernet.generate_key() e "
            "impostala su Render (Environment) prima di collegare account social."
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        raise EncryptionNotConfigured("Impossibile decifrare: ENCRYPTION_KEY errata o cambiata rispetto a quando il dato e' stato salvato")
