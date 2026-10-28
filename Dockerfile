# syntax=docker/dockerfile:1.7
# ============================================================
#  CareerRadar AI · Kişisel İş Radar Paneli
#  Build:  docker build -t careerradar-ai:latest .
#  Run:    docker compose up -d  (iki servis: api + frontend)
# ============================================================

ARG PY_VERSION=3.12
FROM python:${PY_VERSION}-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_HOME=/app \
    TZ=Europe/Istanbul

WORKDIR ${APP_HOME}

# ---- Sistem bağımlılıkları (gzip/brotli decode + PDF parse + sqlite) ----
RUN apt-get update -qq \
 && apt-get install -y --no-install-recommends \
        curl ca-certificates tzdata procps file libmagic1 \
 && ln -snf /usr/share/zoneinfo/${TZ} /etc/localtime \
 && echo ${TZ} > /etc/timezone \
 && rm -rf /var/lib/apt/lists/*

# ---- Python bağımlılıkları (katman cache) ----
COPY apps/api/requirements.txt      ./apps/api/requirements.txt
COPY apps/frontend/requirements.txt ./apps/frontend/requirements.txt

RUN  pip install --upgrade pip setuptools wheel \
 &&  pip install -r ./apps/api/requirements.txt \
 &&  pip install -r ./apps/frontend/requirements.txt \
 # Opsiyonel: brotli + cloudscraper + playwright (bot koruması bypass)
 &&  pip install brotli cloudscraper playwright \
 # Playwright tarayıcılarını kurmak isterseniz AŞAĞIDAKİ satırı UNCOMMENT yap (≈300MB):
 # &&  playwright install chromium \
 &&  true

# ---- Uygulama kodunu kopyala ----
COPY apps/api                    ./apps/api
COPY apps/frontend               ./apps/frontend
COPY scripts/dev_start.sh        ./scripts/dev_start.sh  2>/dev/null || true
COPY scripts/dev_stop.sh         ./scripts/dev_stop.sh   2>/dev/null || true

# ---- Runtime kullanıcısı (root değil) ----
RUN useradd -m -u 1000 -s /bin/bash app \
 && mkdir -p ${APP_HOME}/apps/api/app/storage \
 && chown -R 1000:1000 ${APP_HOME}

USER 1000

# SQLite DB + storage state, konteyner dışında kalıcı tutulacak VOLUME mount noktası
VOLUME ["/app/apps/api"]

EXPOSE 8000 8501

HEALTHCHECK --interval=45s --timeout=8s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/healthz || curl -fsS http://127.0.0.1:8501/_stcore/health || exit 1

# Varsayılan (build denemesi için): help mesajı
CMD [ "/bin/bash", "-c", "echo CareerRadar AI Image OK. Kullanım: docker compose up (api + frontend ayrı servisler)" ]
