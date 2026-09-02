#!/usr/bin/env python3
"""
Monitoraggio CFD (Centro Funzionale Decentrato) della Regione Veneto.

Scarica la pagina CFD, estrae i link ai PDF AAR e AVM,
li scarica e li invia su Telegram se nuovi o aggiornati.

Stato persistente in cfd/state.json per evitare doppi invii.
"""

import json
import re
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

import config

# ── Logging ──────────────────────────────────────────────────────────────
log_mode = "w" if datetime.now().isoweekday() == 1 else "a"


def log(msg: str):
    """Scrive un messaggio sul file di log CFD."""
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    try:
        with open(config.CFD_LOG, log_mode, encoding="utf-8") as f:
            f.write(f"{timestamp} {msg}\n")
    except Exception:
        pass
    print(f"{timestamp} {msg}")


# ── Stato ────────────────────────────────────────────────────────────────
def load_state() -> dict:
    """Carica lo stato dei PDF già inviati."""
    if config.CFD_STATE_JSON.exists():
        try:
            return json.loads(config.CFD_STATE_JSON.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            log(f"Errore lettura state.json: {e}")
    return {}


def save_state(state: dict):
    """Salva lo stato dei PDF inviati."""
    try:
        config.CFD_STATE_JSON.write_text(
            json.dumps(state, indent=4, ensure_ascii=False), encoding="utf-8",
        )
    except OSError as e:
        log(f"Errore scrittura state.json: {e}")


# ── Parser pagina CFD ───────────────────────────────────────────────────
def parse_cfd_page() -> list[dict]:
    """Scarica la pagina CFD ed estrae i link ai PDF AAR e AVM."""
    try:
        r = requests.get(config.CFD_PAGE_URL, timeout=config.REQUESTS_TIMEOUT)
        r.raise_for_status()
    except requests.RequestException as e:
        log(f"Errore caricamento pagina CFD: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    documents = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        match = re.search(r"/(AAR|AVM)_(\d{6})\.pdf", href)
        if not match:
            continue
        prefix = match.group(1)
        date_str = match.group(2)
        filename = f"{prefix}_{date_str}_CFD.pdf"
        numero_match = re.search(r"n\.\s*(\d+)/2026", text)
        numero = int(numero_match.group(1)) if numero_match else 0
        full_url = href if href.startswith("http") else f"https://www.regione.veneto.it{href}"
        documents.append({
            "filename": filename, "url": full_url, "title": text,
            "numero": numero, "prefix": prefix, "date": date_str,
        })

    documents.sort(key=lambda d: d["numero"], reverse=True)
    return documents


# ── Download e invio ─────────────────────────────────────────────────────
def get_last_modified(url: str) -> str:
    """Recupera l'header Last-Modified tramite HEAD."""
    try:
        r = requests.head(url, timeout=config.REQUESTS_TIMEOUT)
        return r.headers.get("Last-Modified", "")
    except requests.RequestException as e:
        log(f"Errore HEAD {url}: {e}")
        return ""


def download_and_send(pdf_info: dict) -> dict | None:
    """Scarica il PDF e lo invia su Telegram."""
    filename = pdf_info["filename"]
    url = pdf_info["url"]
    title = pdf_info["title"]
    local_path = config.CFD_DIR / filename
    today_human = datetime.now().strftime("%d/%m/%Y")

    log(f"Trovato nuovo file: {filename} - {title}")

    try:
        r = requests.get(url, stream=True, timeout=config.REQUESTS_TIMEOUT)
        if (r.status_code != 200
                or not r.headers.get("Content-Type", "").startswith("application/pdf")):
            log(f"PDF non valido per {filename}: HTTP {r.status_code}")
            return None

        last_modified = r.headers.get("Last-Modified", "")

        with open(local_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        log(f"Scaricato PDF: {filename} ({len(r.content)} bytes)")

        if not config.TOKEN:
            log("⚠️  TELEGRAM_TOKEN non impostato, invio PDF saltato.")
            return None

        caption = f"{title} - {today_human}"
        with open(local_path, "rb") as f:
            resp = requests.post(
                config.telegram_api_url("sendDocument"),
                data={"chat_id": config.CHAT_ID, "caption": caption},
                files={"document": (filename, f)},
                timeout=config.REQUESTS_TIMEOUT,
            )

        if resp.status_code == 200:
            log(f"✅ PDF inviato su Telegram: {filename}")
            return {
                "sent_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_modified": last_modified,
            }
        else:
            log(f"❌ Errore invio Telegram: {resp.status_code} - {resp.text}")
            return None

    except Exception as e:
        log(f"Errore download/invio {filename}: {e}")
        return None


def cleanup_old_pdfs(prefix: str):
    """Tiene solo gli ultimi 2 PDF per prefisso (AAR/AVM)."""
    pdfs = sorted(config.CFD_DIR.glob(f"{prefix}_*_CFD.pdf"), reverse=True)
    for old in pdfs[2:]:
        try:
            old.unlink()
            log(f"Pulito PDF vecchio: {old.name}")
        except OSError as e:
            log(f"Errore pulizia {old.name}: {e}")


# ── Logica principale ───────────────────────────────────────────────────
def process_documents(state: dict) -> list[str]:
    """Esamina la pagina CFD, trova i PDF AAR/AVM non ancora inviati."""
    results = []

    documents = parse_cfd_page()
    if not documents:
        log("Nessun documento trovato sulla pagina CFD.")
        return ["ℹ️ Nessun documento trovato sulla pagina CFD."]

    today_ymd = datetime.now().strftime("%y%m%d")

    docs_to_check = [
        d for d in documents
        if d["prefix"] in ("AAR", "AVM") and d["date"] == today_ymd
    ]
    if not docs_to_check:
        docs_today = [d for d in documents if d["date"] == today_ymd]
        if docs_today:
            altri = set(d["prefix"] for d in docs_today)
            log(f"Oggi ({today_ymd}) disponibili solo: {altri}. Nessun AAR/AVM.")
        else:
            log(f"Nessun documento pubblicato oggi ({today_ymd}).")

    new_docs = []
    for doc in docs_to_check:
        state_key = doc["filename"]
        if state_key not in state:
            new_docs.append(doc)
        else:
            stato_prec = state[state_key]
            old_lm = (
                stato_prec.get("last_modified", "")
                if isinstance(stato_prec, dict) else ""
            )
            current_lm = get_last_modified(doc["url"])
            if old_lm and current_lm and current_lm != old_lm:
                log(f"PDF aggiornato: {doc['filename']} ({old_lm} → {current_lm})")
                new_docs.append(doc)
            else:
                inviato_il = (
                    stato_prec.get("sent_at", stato_prec)
                    if isinstance(stato_prec, dict) else stato_prec
                )
                log(f"Già inviato: {doc['filename']} (inviato il {inviato_il})")

    if not new_docs:
        log("Nessun nuovo documento da inviare.")
        return ["ℹ️ Nessun nuovo documento da inviare."]

    new_docs.sort(key=lambda d: d["prefix"])
    for doc in new_docs:
        res = download_and_send(doc)
        if res is not None:
            results.append(f"✅ Inviato: {doc['filename']} ({doc['title']})")
            state[doc["filename"]] = res
            cleanup_old_pdfs(doc["prefix"])
        else:
            results.append(f"❌ Errore: {doc['filename']}")
            state[doc["filename"]] = {
                "sent_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_modified": "", "error": True,
            }

    return results


# ── Entry point ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    config.ensure_dirs()
    current_state = load_state()
    results = process_documents(current_state)
    save_state(current_state)
    for r in results:
        print(r)
