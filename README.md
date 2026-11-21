# ÇEŞME MARKET 2 – DİJİTAL KATALOG VE MAĞAZADAN TESLİM SİPARİŞ PLATFORMU

Masaüstü ve mobil tarayıcılarda çalışan ürün kataloğu, çevrimiçi sipariş, mağazadan teslim ve mağazada ödeme akışları ile mağaza yönetim paneli.

## Mimari ve Teknoloji

- **Frontend:** TypeScript, Vite ve modern HTML5.
- **Backend:** Python 3.11+, FastAPI, SQLAlchemy 2.0 ve Pydantic v2.
- **Veritabanı:** Yerel kullanımda SQLite (`cesme_market2.db`); üretimde `.env` üzerinden PostgreSQL (`DATABASE_URL`).
- **Güvenlik:** PBKDF2-HMAC-SHA256 parola özeti, JWT oturumları, rol tabanlı yetkilendirme, sunucu tarafı fiyat kontrolü, çift sipariş önleme, istek sınırlandırma ve yükleme doğrulaması.

## Kurulum ve Çalıştırma

Ön gereksinimler: Python 3.11+, Node.js 20+ ve npm. `.env.example` dosyasını `.env` olarak kopyalayıp düzenleyin. Mağaza iletişim alanları için `STORE_ADDRESS`, `STORE_PHONE`, `STORE_WHATSAPP` (ülke koduyla, yalnızca rakam) ve `STORE_MAPS_URL` değerlerini ayarlayın.

Tek sunucudan API ve web arayüzünü `http://127.0.0.1:8000` adresinde çalıştırmak için:

```powershell
npm install
npm run build
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Geliştirme modunda Vite (`http://localhost:5173`) ve FastAPI'yi (`http://127.0.0.1:8000`) ayrı terminallerde başlatın:

```powershell
# Terminal 1
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000

# Terminal 2
npm run dev
```

## Yönetim Paneli

Üst menüdeki **Yönetim Paneli** düğmesinden giriş yapılır:

| Rol | Kullanıcı adı | Yerel varsayılan parola | Yetkiler |
| --- | --- | --- | --- |
| Mağaza yöneticisi (`ADMIN`) | `admin` | `CesmeAdmin2026!` | Sipariş yönetimi, ürün ve fiyat düzenleme, Excel/CSV içe/dışa aktarma |
| Mağaza personeli (`STAFF`) | `personel` | `CesmePersonel2026!` | Siparişleri görüntüleme, onaylama, hazırlama ve teslim durumunu güncelleme |

Üretim ortamında varsayılan parolaları ortam değişkenleriyle değiştirin.

## API ve Bakım

Sunucu çalışırken [Swagger UI](http://127.0.0.1:8000/docs) veya [ReDoc](http://127.0.0.1:8000/redoc) kullanılabilir.

Pytest ile kontroller:

```powershell
.\.venv\Scripts\pytest.exe -v
```

Veritabanı yedekleme ve geri yükleme:

```powershell
.\.venv\Scripts\python.exe scripts/backup_restore.py backup
.\.venv\Scripts\python.exe scripts/backup_restore.py restore <yedek_dosya_adi.db>
```
