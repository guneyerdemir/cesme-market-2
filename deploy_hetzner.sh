#!/usr/bin/env bash
# =============================================================================
# ÇEŞME MARKET 2 – HETZNER + CLOUDFLARE TEK KOMUTLA CANLIYA ALMA SCRİPTİ
# Subdomain: cesmemarket.guneyerdemir.com
# Sunucu IP: 2.29.154.116
# Kullanım:  sudo bash deploy_hetzner.sh
# =============================================================================
set -euo pipefail

DOMAIN="${DOMAIN:-cesmemarket.guneyerdemir.com}"
REPO_URL="https://github.com/guneyerdemir/cesme-market-2.git"
APP_DIR="/var/www/cesme-market-2"
SERVICE_NAME="cesme-market-2"
APP_PORT="${APP_PORT:-8022}"

echo "======================================================================"
echo " ÇEŞME MARKET 2 - OTOMATİK KURULUM VE CANLIYA ALMA BAŞLIYOR"
echo " Domain   : https://${DOMAIN}"
echo " Dizin    : ${APP_DIR}"
echo " İç Port  : 127.0.0.1:${APP_PORT}"
echo "======================================================================"

if [ "$(id -u)" -ne 0 ]; then
  echo "[HATA] Lütfen bu scripti root olarak veya 'sudo bash deploy_hetzner.sh' ile çalıştırın."
  exit 1
fi

# 1. Sistem paketlerini kontrol et ve eksikleri kur (Python, Node.js, Nginx, Git, Certbot)
echo "[1/7] Sistem paketleri (Python3, Nginx, Git, Certbot) kontrol ediliyor..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y git curl ca-certificates gnupg python3 python3-venv python3-pip nginx certbot python3-certbot-nginx

if ! command -v node >/dev/null 2>&1; then
  echo "[1.1/7] Node.js 20.x kuruluyor..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi

echo "      Python sürümü : $(python3 --version)"
echo "      Node sürümü   : $(node --version)"
echo "      NPM sürümü    : $(npm --version)"

# 2. Projeyi GitHub'dan çek veya mevcutsa güncelle
echo "[2/7] GitHub reposu (${REPO_URL}) hazırlanıyor..."
mkdir -p /var/www
if [ -d "${APP_DIR}/.git" ]; then
  echo "      Mevcut repo bulundu, 'git pull' ile güncelleniyor..."
  cd "${APP_DIR}"
  git fetch origin main
  git reset --hard origin/main
else
  echo "      Repo ${APP_DIR} dizinine klonlanıyor..."
  git clone "${REPO_URL}" "${APP_DIR}"
  cd "${APP_DIR}"
fi

# 3. .env dosyasını oluştur (Eğer daha önce oluşturulmamışsa)
echo "[3/7] Ortam değişkenleri (.env) kontrol ediliyor..."
if [ ! -f "${APP_DIR}/.env" ]; then
  RANDOM_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  cat > "${APP_DIR}/.env" <<EOF
APP_ENV=production
APP_NAME="Çeşme Market 2 - Dijital Mağaza"
SECRET_KEY=${RANDOM_SECRET}
ACCESS_TOKEN_EXPIRE_MINUTES=720
DATABASE_URL=sqlite:///${APP_DIR}/cesme_market2.db
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD=CesmeAdmin2026!
INITIAL_STAFF_USERNAME=personel
INITIAL_STAFF_PASSWORD=CesmePersonel2026!
ENABLE_SMS_NOTIFICATIONS=false
ENABLE_WHATSAPP_NOTIFICATIONS=false
EOF
  chmod 600 "${APP_DIR}/.env"
  echo "      Yeni .env dosyası güvenli SECRET_KEY ile oluşturuldu."
else
  echo "      Mevcut .env dosyası korundu."
fi

# 4. Frontend (Vite + TypeScript) derlemesi
echo "[4/7] Frontend bağımlılıkları kuruluyor ve 'dist/' klasörü derleniyor..."
cd "${APP_DIR}"
npm install
npm run build

# 5. Python sanal ortamı (.venv) ve FastAPI bağımlılıkları
echo "[5/7] Python sanal ortamı (.venv) ve backend paketleri kuruluyor..."
if [ ! -d "${APP_DIR}/.venv" ]; then
  python3 -m venv "${APP_DIR}/.venv"
fi
"${APP_DIR}/.venv/bin/pip" install --upgrade pip
"${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

# 6. Systemd servisi oluştur ve başlat
echo "[6/7] Systemd servisi (${SERVICE_NAME}.service) yapılandırılıyor..."
cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=Cesme Market 2 - Online Siparis ve Magaza Yonetim Platformu
After=network.target

[Service]
User=root
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port ${APP_PORT} --workers 2
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

# 7. Nginx Reverse Proxy ayarı
echo "[7/7] Nginx (${DOMAIN}) reverse proxy yapılandırılıyor..."
cat > "/etc/nginx/sites-available/${DOMAIN}" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};

    client_max_body_size 20M;

    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

ln -sf "/etc/nginx/sites-available/${DOMAIN}" "/etc/nginx/sites-enabled/${DOMAIN}"
nginx -t
systemctl reload nginx

echo ""
echo "======================================================================"
echo " ✅ KURULUM TAMAMLANDI!"
echo "----------------------------------------------------------------------"
echo " 🌐 Canlı Adres       : https://${DOMAIN} (veya http://${DOMAIN})"
echo " 🔐 Yönetim Paneli    : Üst menüden 'Yönetim Paneli' butonuna tıklayın"
echo "    - Yönetici Girişi : admin / CesmeAdmin2026!"
echo "    - Personel Girişi : personel / CesmePersonel2026!"
echo "----------------------------------------------------------------------"
echo " İPUCU (SSL / HTTPS):"
echo " - Cloudflare üzerinde Proxy (Turuncu Bulut) açıksa ve SSL/TLS modu"
echo "   'Flexible' veya 'Full' ise https://${DOMAIN} doğrudan çalışır."
echo " - Sunucuya Let's Encrypt SSL sertifikası da kurmak isterseniz:"
echo "   sudo certbot --nginx -d ${DOMAIN}"
echo "======================================================================"
