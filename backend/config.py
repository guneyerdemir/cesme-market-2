import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
load_dotenv(BASE_DIR / ".env")

APP_ENV = os.getenv("APP_ENV", "development")
APP_NAME = os.getenv("APP_NAME", "Çeşme Market 2 - Dijital Katalog")
STORE_ADDRESS = os.getenv("STORE_ADDRESS", "")
STORE_PHONE = os.getenv("STORE_PHONE", "")
STORE_WHATSAPP = os.getenv("STORE_WHATSAPP", "")
STORE_MAPS_URL = os.getenv("STORE_MAPS_URL", "")
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "cesme_market_2_local_dev_secret_key_change_in_production_2026",
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'cesme_market2.db'}")

INITIAL_ADMIN_USERNAME = os.getenv("INITIAL_ADMIN_USERNAME", "admin")
INITIAL_ADMIN_PASSWORD = os.getenv("INITIAL_ADMIN_PASSWORD", "CesmeAdmin2026!")
INITIAL_STAFF_USERNAME = os.getenv("INITIAL_STAFF_USERNAME", "personel")
INITIAL_STAFF_PASSWORD = os.getenv("INITIAL_STAFF_PASSWORD", "CesmePersonel2026!")

ENABLE_SMS_NOTIFICATIONS = os.getenv("ENABLE_SMS_NOTIFICATIONS", "false").lower() == "true"
ENABLE_WHATSAPP_NOTIFICATIONS = os.getenv("ENABLE_WHATSAPP_NOTIFICATIONS", "false").lower() == "true"
