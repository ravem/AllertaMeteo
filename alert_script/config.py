"""
Configurazione centralizzata per il sistema allerte meteo (versione server).
Le variabili sensibili (TOKEN, CHAT_ID) vengono caricate da variabili d'ambiente
con fallback su file .env nella directory del progetto.
"""

import os
import sys
from pathlib import Path

# Carica .env se presente (supporta sia dotenv che parsing manuale)
ENV_PATH = Path(__file__).resolve().parent / ".env"
if ENV_PATH.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(ENV_PATH)
    except ImportError:
        # Fallback manuale se dotenv non installato
        import re
        with open(ENV_PATH) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

# Directory radice del progetto (dove si trova questo file)
ROOT_DIR = Path(__file__).resolve().parent

# ── Path assoluti calcolati ──────────────────────────────────────────────
DATA_DIR = ROOT_DIR / "data"
BOLLETTINI_DIR = DATA_DIR / "bollettini"
ZONE_DIR = DATA_DIR / "zone"
CFD_DIR = ROOT_DIR / "cfd"
TMP_DIR = ROOT_DIR / "tmp"

# ── File di stato e log ──────────────────────────────────────────────────
ALERT_TXT = ROOT_DIR / "alert.txt"
ALERT_OLD_TXT = ROOT_DIR / "alert_old.txt"
ALERT_LOG = ROOT_DIR / "alert.log"
LASTRUN_TXT = ROOT_DIR / "lastrun.txt"
SEND_MESSAGE_LOG = ROOT_DIR / "send_message.log"
SENT_NOTIFICATIONS_JSON = ROOT_DIR / "sent_notifications.json"
CFD_STATE_JSON = CFD_DIR / "state.json"
API_SERVER_LOG = ROOT_DIR / "api_server.log"
API_SERVER_ERROR_LOG = ROOT_DIR / "api_server_error.log"
BOT_LISTENER_LOG = ROOT_DIR / "bot_listener.log"
BOT_LISTENER_ERROR_LOG = ROOT_DIR / "bot_listener_error.log"
BOT_OFFSET_FILE = ROOT_DIR / "bot_offset.txt"
BOT_LOCK_FILE = ROOT_DIR / "bot_listener.lock"

# ── Telegram ─────────────────────────────────────────────────────────────
TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

if not TOKEN:
    print("⚠️  ATTENZIONE: TELEGRAM_TOKEN non impostato. "
          "Crea un file .env con TELEGRAM_TOKEN=...", file=sys.stderr)
if not CHAT_ID:
    print("⚠️  ATTENZIONE: TELEGRAM_CHAT_ID non impostato. "
          "Crea un file .env con TELEGRAM_CHAT_ID=...", file=sys.stderr)

# ── URL esterne ──────────────────────────────────────────────────────────
PROTEZIONE_CIVILE_BOLLETTINI_URL = (
    "https://github.com/pcm-dpc/DPC-Bollettini-Criticita-Idrogeologica-Idraulica"
    "/blob/master/files/all/latest_all.zip?raw=true"
)
COMUNI_ITALIANI_URL = (
    "https://raw.githubusercontent.com/opendatasicilia/comuni-italiani/main/dati/main.csv"
)

# ── Alert da monitorare ──────────────────────────────────────────────────
ALERT_KEYWORDS = ["GIALLA", "ARANCIONE", "ROSSA"]
ZONA_DEFAULT = "Vene-E"        # zona predefinita per estrazione
COMUNE_DEFAULT = "Padova"      # comune predefinito per estrazione

# ── Path HTML output ────────────────────────────────────────────────────
# Dove viene generata la pagina HTML (configurabile via env per flessibilità)
HTML_PATH = Path(os.getenv("ALERT_HTML_PATH", str(ROOT_DIR.parent / "web" / "alert" / "index.html")))

# ── Timeout richieste HTTP ───────────────────────────────────────────────
REQUESTS_TIMEOUT = 15

# ── Pulizia log ─────────────────────────────────────────────────────────
LOG_CLEANUP_MAX_SIZE_MB = 1
LOG_CLEANUP_KEEP_LINES = 500


# ── Utilità ──────────────────────────────────────────────────────────────
def ensure_dirs():
    """Crea le directory necessarie se non esistono."""
    for d in [DATA_DIR, BOLLETTINI_DIR, ZONE_DIR, CFD_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def telegram_api_url(method: str = "sendMessage") -> str:
    """Restituisce l'URL completo per una chiamata all'API Telegram."""
    return f"https://api.telegram.org/bot{TOKEN}/{method}"
