import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
load_dotenv(BASE_DIR / ".env")

APP_ENV = os.getenv("APP_ENV", "development")
APP_NAME = os.getenv("APP_NAME", "Çeşme Market 2 - Dijital Katalog")

DEFAULT_STORE_ADDRESS = "Narlı Mh. Çelebi Sk. No: 53/B Narlıdere/İZMİR"
DEFAULT_STORE_PHONE = "05396194888"
DEFAULT_STORE_WHATSAPP = "905396194888"
DEFAULT_STORE_MAPS_URL = (
    "https://www.google.com.ua/maps/place/%C3%87e%C5%9Fme+Market+2+Narlidere/"
    "@38.392522,27.0020049,17z/data=!4m14!1m7!3m6!1s0x14bbddda609a4c8d:0x32918fd2f32fb7e4!"
    "2s%C3%87e%C5%9Fme+Market+2+Narlidere!8m2!3d38.3925178!4d27.0045798!16s%2Fg%2F11j3r4c3_8!"
    "3m5!1s0x14bbddda609a4c8d:0x32918fd2f32fb7e4!8m2!3d38.3925178!4d27.0045798!"
    "16s%2Fg%2F11j3r4c3_8?entry=ttu&g_ep=EgoyMDI2MTExOC4xIKXMDSoASAFQAw%3D%3D"
)

STORE_ADDRESS = os.getenv("STORE_ADDRESS", DEFAULT_STORE_ADDRESS) or DEFAULT_STORE_ADDRESS
STORE_PHONE = os.getenv("STORE_PHONE", DEFAULT_STORE_PHONE) or DEFAULT_STORE_PHONE
STORE_WHATSAPP = os.getenv("STORE_WHATSAPP", DEFAULT_STORE_WHATSAPP) or DEFAULT_STORE_WHATSAPP
STORE_MAPS_URL = os.getenv("STORE_MAPS_URL", DEFAULT_STORE_MAPS_URL) or DEFAULT_STORE_MAPS_URL

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
