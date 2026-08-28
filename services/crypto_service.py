import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from dotenv import find_dotenv, set_key

from utils.logger import get_logger

logger = get_logger("crypto_service")

ENV_PATH = find_dotenv() or str(Path(".env"))
KEY_NAME = "FERNET_MASTER_KEY"


def _ensure_env_file() -> str:
    path = Path(ENV_PATH)
    if not path.exists():
        path.write_text("")
    return str(path)


def get_or_create_master_key() -> bytes:
    env_path = _ensure_env_file()
    existing = os.getenv(KEY_NAME, "").strip()
    if existing:
        return existing.encode()
    key = Fernet.generate_key()
    set_key(env_path, KEY_NAME, key.decode())
    os.environ[KEY_NAME] = key.decode()
    logger.info("Fernet master key generată și salvată în .env")
    return key


def _fernet() -> Fernet:
    return Fernet(get_or_create_master_key())


def encrypt_password(plain_text: str) -> str:
    if not plain_text:
        return ""
    return _fernet().encrypt(plain_text.encode()).decode()


def decrypt_password(cipher_text: str) -> str:
    if not cipher_text:
        return ""
    try:
        return _fernet().decrypt(cipher_text.encode()).decode()
    except (InvalidToken, ValueError, TypeError):
        return cipher_text
