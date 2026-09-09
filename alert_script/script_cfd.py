#!/usr/bin/env python3
"""
Monitoraggio CFD (Centro Funzionale Decentrato) della Regione Veneto.

Scarica i PDF BVM e BAR direttamente dall'URL della Regione Veneto,
generando il nome file basato sulla data corrente.

Le URL hanno formato:
  https://www.regione.veneto.it/documents/90748/14376036/{PREFIX}_{YYMMDD}_CFD.pdf

Stato persistente in cfd/state.json per evitare doppi invii.
"""

import json
from datetime import datetime, timedelta

import requests

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


# ── Generazione URL ─────────────────────────────────────────────────────
def genera_url_cfd(prefisso: str, data: str) -> str:
    """Genera l'URL per un PDF CFD dato il prefisso e la data YYMMDD."""
    return f"{config.CFD_BASE_URL}/{prefisso}_{data}_CFD.pdf"


def cerca_pdf_disponibili() -> list[dict]:
    """
    Cerca PDF CFD provando prima oggi, poi ieri, poi gli ultimi 7 giorni.
    Restituisce una lista di dict con filename, url, prefisso, data.
    """
    oggi = datetime.now()
    documenti = []

    # Prova oggi, ieri, e fino a 7 giorni indietro
    for giorni_indietro in range(8):
        data = (oggi - timedelta(days=giorni_indietro)).strftime("%y%m%d")
        for prefisso in config.CFD_PREFIXES:
            url = genera_url_cfd(prefisso, data)
            try:
                r = requests.head(url, timeout=config.REQUESTS_TIMEOUT)
                if r.status_code == 200:
                    ct = r.headers.get("Content-Type", "")
                    if "pdf" in ct:
                        filename = f"{prefisso}_{data}_CFD.pdf"
                        documenti.append({
                            "filename": filename,
                            "url": url,
                            "title": f"{prefisso} {data}",
                            "prefisso": prefisso,
                            "data": data,
                        })
                        log(f"Trovato PDF: {filename}")
            except requests.RequestException:
                continue

    return documenti


# ── Download e invio ─────────────────────────────────────────────────────
def download_and_send(pdf_info: dict) -> dict | None:
    """Scarica il PDF e lo invia su Telegram."""
    filename = pdf_info["filename"]
    url = pdf_info["url"]
    title = pdf_info["title"]
    local_path = config.CFD_DIR / filename
    today_human = datetime.now().strftime("%d/%m/%Y")

    log(f"Scaricamento: {filename}")

    try:
        r = requests.get(url, stream=True, timeout=config.REQUESTS_TIMEOUT)
        if (r.status_code != 200
                or not r.headers.get("Content-Type", "").startswith("application/pdf")):
            log(f"PDF non valido per {filename}: HTTP {r.status_code}")
            return None

        last_modified = r.headers.get("Last-Modified", "")

        dimensione = 0
        with open(local_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    dimensione += len(chunk)
        log(f"Scaricato PDF: {filename} ({dimensione} bytes)")

        if not config.TOKEN:
            log("TELEGRAM_TOKEN non impostato, invio PDF saltato.")
            return None

        # Invia il PDF usando subscriptions (broadcast a tutti gli iscritti)
        # oppure usa CHAT_ID per retrocompatibilità
        chat_ids = _get_destinatari()
        if not chat_ids:
            log("Nessun destinatario per l'invio PDF.")
            return None

        caption = f"Bollettino CFD {title} - {today_human}"
        inviato = False
        for chat_id in chat_ids:
            with open(local_path, "rb") as f:
                resp = requests.post(
                    config.telegram_api_url("sendDocument"),
                    data={"chat_id": chat_id, "caption": caption},
                    files={"document": (filename, f)},
                    timeout=config.REQUESTS_TIMEOUT,
                )
            if resp.status_code == 200:
                log(f"PDF inviato a {chat_id}: {filename}")
                inviato = True
            else:
                log(f"Errore invio a {chat_id}: {resp.status_code} - {resp.text[:100]}")

        if inviato:
            return {
                "sent_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_modified": last_modified,
            }
        else:
            return None

    except Exception as e:
        log(f"Errore download/invio {filename}: {e}")
        return None


def _get_destinatari() -> list[int]:
    """
    Restituisce la lista di chat_id a cui inviare i PDF CFD.
    Il destinatario è configurato in config.py (CFD_CHAT_ID)
    o via variabile d'ambiente / .env.
    """
    return [config.CFD_CHAT_ID]


def cleanup_old_pdfs(prefisso: str):
    """Tiene solo gli ultimi 2 PDF per prefisso (BVM/BAR)."""
    pdfs = sorted(config.CFD_DIR.glob(f"{prefisso}_*_CFD.pdf"), reverse=True)
    for old in pdfs[2:]:
        try:
            old.unlink()
            log(f"Pulito PDF vecchio: {old.name}")
        except OSError as e:
            log(f"Errore pulizia {old.name}: {e}")


# ── Logica principale ───────────────────────────────────────────────────
def process_documents(state: dict) -> list[str]:
    """Cerca PDF CFD non ancora inviati e li scarica/invia."""
    results = []

    documenti = cerca_pdf_disponibili()
    if not documenti:
        log("Nessun PDF CFD trovato.")
        return ["Nessun PDF CFD trovato."]

    nuovi = []
    for doc in documenti:
        state_key = doc["filename"]
        if state_key not in state:
            nuovi.append(doc)
        else:
            log(f"Gia inviato: {doc['filename']}")

    if not nuovi:
        log("Nessun nuovo PDF CFD da inviare.")
        return ["Nessun nuovo PDF CFD da inviare."]

    for doc in nuovi:
        res = download_and_send(doc)
        if res is not None:
            results.append(f"Inviato: {doc['filename']}")
            state[doc["filename"]] = res
            cleanup_old_pdfs(doc["prefisso"])
        else:
            results.append(f"Errore: {doc['filename']}")
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
