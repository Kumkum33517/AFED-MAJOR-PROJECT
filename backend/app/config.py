"""Environment configuration. Plain constants: there is one deployment shape, not a config framework."""
import os
import re
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR.parent / ".env")

MODELS_DIR = BACKEND_DIR / "models_store"
UPLOAD_DIR = BACKEND_DIR / "data" / "uploads"
DATASET_CSV = BACKEND_DIR / "data" / "afed_transactions.csv"

_url = os.getenv("DATABASE_URL", "").strip()
# Hosts hand out postgres:// or postgresql://. Name the driver: SQLAlchemy dropped the first
# spelling, and since 2.1 the second means psycopg 3, which is not what requirements.txt installs.
DATABASE_URL = re.sub(r"^postgres(ql)?://", "postgresql+psycopg2://", _url) if _url else f"sqlite:///{BACKEND_DIR / 'afed.db'}"
IS_SQLITE = DATABASE_URL.startswith("sqlite")

_DEV_SECRET = "dev-only-secret-change-me-in-production"
# "or": a blank value, as a copied .env.example has, must count as unset. An empty signing key lets anyone mint tokens.
JWT_SECRET = os.getenv("JWT_SECRET", "").strip() or _DEV_SECRET
if not IS_SQLITE and (JWT_SECRET == _DEV_SECRET or len(JWT_SECRET) < 32):
    # A real database with a guessable signing key would let anyone mint an Admin token.
    raise RuntimeError("JWT_SECRET must be set, at least 32 characters, when DATABASE_URL points at a real database. "
                       "Generate one with: openssl rand -hex 32")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "720"))

CORS_ORIGINS = [o.strip() for o in os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]

QWEN_PROVIDER = os.getenv("QWEN_PROVIDER", "template")
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
# Proxies in front of the API that append to X-Forwarded-For (Render: 1). 0 trusts no header: a client can write it.
TRUSTED_PROXY_HOPS = int(os.getenv("TRUSTED_PROXY_HOPS", "0"))
MAX_BODY_BYTES = 1024 * 1024  # every request except a CSV upload
UPLOAD_MAX_AGE_HOURS = 24
