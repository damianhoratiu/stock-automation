import os
from pathlib import Path
from dotenv import load_dotenv, set_key, find_dotenv

# Valori implicite Auto-Connect pentru Supabase
DEFAULT_SUPABASE_URL = "https://fdsuyapjlrhlqpvcwmqh.supabase.co"
DEFAULT_SUPABASE_KEY = "sb_publishable_LFYDGVvxkWt1KwiWXl_Sag_s12i_3xl"

# Încercăm să găsim sau să creăm fișierul .env
ENV_PATH = find_dotenv()
if not ENV_PATH:
    ENV_PATH = Path(".env")
    if not ENV_PATH.exists():
        ENV_PATH.write_text("")

load_dotenv(ENV_PATH)

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
if not SUPABASE_URL:
    SUPABASE_URL = DEFAULT_SUPABASE_URL
    set_key(str(ENV_PATH), "SUPABASE_URL", SUPABASE_URL)

SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()
if not SUPABASE_KEY:
    SUPABASE_KEY = DEFAULT_SUPABASE_KEY
    set_key(str(ENV_PATH), "SUPABASE_KEY", SUPABASE_KEY)

PHOTOTAG_API_KEY = os.getenv("PHOTOTAG_API_KEY", "")

PHOTOS_BASE_DIR = os.getenv("PHOTOS_BASE_DIR", "./photos")

FTP_ADOBE_HOST = os.getenv("FTP_ADOBE_HOST", "")
FTP_ADOBE_USER = os.getenv("FTP_ADOBE_USER", "")
FTP_ADOBE_PASS = os.getenv("FTP_ADOBE_PASS", "")

FTP_SHUTTER_HOST = os.getenv("FTP_SHUTTER_HOST", "")
FTP_SHUTTER_USER = os.getenv("FTP_SHUTTER_USER", "")
FTP_SHUTTER_PASS = os.getenv("FTP_SHUTTER_PASS", "")

PHOTOTAG_API_URL = "https://server.phototag.ai/api/keywords"

def bootstrap_environment():
    """Creează automat directoarele locale necesare dacă sunt configurate și valide."""
    if PHOTOS_BASE_DIR:
        Path(PHOTOS_BASE_DIR).mkdir(parents=True, exist_ok=True)
    Path("./logs").mkdir(parents=True, exist_ok=True)

def save_to_env(key: str, value: str):
    """Salvează sau actualizează o cheie în fișierul .env folosind dotenv.set_key."""
    global SUPABASE_URL, SUPABASE_KEY, PHOTOTAG_API_KEY, PHOTOS_BASE_DIR
    global FTP_ADOBE_HOST, FTP_ADOBE_USER, FTP_ADOBE_PASS
    global FTP_SHUTTER_HOST, FTP_SHUTTER_USER, FTP_SHUTTER_PASS

    set_key(str(ENV_PATH), key, value)
    load_dotenv(ENV_PATH, override=True)

    # Actualizăm variabilele globale în memorie
    SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip() or DEFAULT_SUPABASE_URL
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip() or DEFAULT_SUPABASE_KEY
    PHOTOTAG_API_KEY = os.getenv("PHOTOTAG_API_KEY", "")
    PHOTOS_BASE_DIR = os.getenv("PHOTOS_BASE_DIR", "./photos")
    
    FTP_ADOBE_HOST = os.getenv("FTP_ADOBE_HOST", "")
    FTP_ADOBE_USER = os.getenv("FTP_ADOBE_USER", "")
    FTP_ADOBE_PASS = os.getenv("FTP_ADOBE_PASS", "")

    FTP_SHUTTER_HOST = os.getenv("FTP_SHUTTER_HOST", "")
    FTP_SHUTTER_USER = os.getenv("FTP_SHUTTER_USER", "")
    FTP_SHUTTER_PASS = os.getenv("FTP_SHUTTER_PASS", "")

    bootstrap_environment()

bootstrap_environment()
