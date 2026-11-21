"""
Çeşme Market 2 – Veritabanı ve Ürün Görselleri Yedekleme / Geri Yükleme Aracı
Kullanım:
  Yedek almak için:      .\.venv\Scripts\python.exe scripts/backup_restore.py backup
  Geri yüklemek için:    .\.venv\Scripts\python.exe scripts/backup_restore.py restore <yedek_dosya_adi.db>
"""
import shutil
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "cesme_market2.db"
BACKUP_DIR = BASE_DIR / "backups"


def create_backup() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Veritabanı dosyası bulunamadı: {DB_PATH}")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"cesme_market2_backup_{stamp}.db"
    shutil.copy2(DB_PATH, dest)
    print(f"[OK] Veritabanı yedeği oluşturuldu: {dest}")
    return dest


def restore_backup(filename: str) -> None:
    src = BACKUP_DIR / filename
    if not src.exists():
        raise FileNotFoundError(f"Yedek dosyası bulunamadı: {src}")
    shutil.copy2(src, DB_PATH)
    print(f"[OK] Veritabanı geri yüklendi: {src} -> {DB_PATH}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "backup"
    if cmd == "backup":
        create_backup()
    elif cmd == "restore" and len(sys.argv) > 2:
        restore_backup(sys.argv[2])
    else:
        print("Kullanım: python scripts/backup_restore.py [backup | restore <dosya_adi>]")
