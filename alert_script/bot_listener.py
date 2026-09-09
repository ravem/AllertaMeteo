#!/usr/bin/env python3
"""
Listener per il bot Telegram.
Elabora i comandi /subscribe, /start, /cancella, /mio_comune, /liste, /help
e attiva le iscrizioni. Supporta MULTIPLE iscrizioni per utente.

Modalità:
  python3 bot_listener.py           → singolo ciclo (per cron)
  python3 bot_listener.py --daemon  → esecuzione continua (per systemd/screen)
"""

import os
import sys
import time
import json

import requests

import config
from subscriptions import (
    activate_subscription, cleanup_expired,
    get_user_subscriptions, remove_subscription_by_index, remove_all_subscriptions,
)

# ── Logging ──────────────────────────────────────────────────────────────
def log(msg: str):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    try:
        with open(config.BOT_LISTENER_LOG, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} {msg}\n")
    except Exception:
        pass
    print(f"{timestamp} {msg}")


# ── Anti-duplicato in sessione ──────────────────────────────────────────
_processed_ids = set()


# ── Offset polling ──────────────────────────────────────────────────────
def get_last_offset() -> int:
    try:
        return int(config.BOT_OFFSET_FILE.read_text().strip())
    except (IOError, ValueError):
        return 0


def save_last_offset(offset: int):
    try:
        config.BOT_OFFSET_FILE.write_text(str(offset))
    except OSError as e:
        log(f"Errore salvataggio offset: {e}")


# ── Utility Telegram ────────────────────────────────────────────────────
def send_message(chat_id: int, text: str) -> bool:
    if not config.TOKEN:
        log("⚠️  TELEGRAM_TOKEN non impostato, messaggio non inviato.")
        return False
    try:
        resp = requests.post(
            config.telegram_api_url("sendMessage"),
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=config.REQUESTS_TIMEOUT,
        )
        return resp.status_code == 200
    except requests.RequestException as e:
        log(f"Errore invio messaggio a {chat_id}: {e}")
        return False


# ── Processazione update ────────────────────────────────────────────────
def process_update(update: dict) -> int | None:
    update_id = update.get("update_id")

    # Anti-duplicato in sessione
    if update_id in _processed_ids:
        return update_id
    _processed_ids.add(update_id)

    msg = update.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text = (msg.get("text") or "").strip()
    username = msg.get("from", {}).get("username", "")

    if not chat_id or not text:
        return update_id

    # /start
    if text.startswith("/start"):
        welcome = (
            "👋 Benvenuto! Sono il bot delle <b>Allerte Meteo</b>.\n\n"
            "Per iscriverti:\n"
            "1. Vai sulla pagina di iscrizione del sito\n"
            "2. Seleziona il tuo comune\n"
            "3. Ottieni un codice di iscrizione\n"
            "4. Inviami il comando:\n\n"
            "<code>/subscribe CODICE</code>\n\n"
            "Esempio: <code>/subscribe SUB-A3F2K9</code>\n\n"
            "<i>Il codice è valido per 24 ore.</i>\n\n"
            "Comandi disponibili:\n"
            "/start — Questo messaggio\n"
            "/subscribe CODICE — Attiva l'iscrizione\n"
            "/mio_comune — Mostra le tue iscrizioni\n"
            "/liste — Elenca le tue iscrizioni\n"
            "/cancella N — Cancella l'iscrizione numero N\n"
            "/cancella_tutto — Cancella tutte le iscrizioni\n"
            "/help — Aiuto"
        )
        send_message(chat_id, welcome)
        log(f"Benvenuto inviato a {chat_id} (@{username})")
        return update_id

    # /subscribe CODICE
    if text.startswith("/subscribe"):
        parts = text.split()
        if len(parts) < 2:
            send_message(
                chat_id,
                "⚠️ Uso: <code>/subscribe CODICE</code>\n"
                "Esempio: <code>/subscribe SUB-A3F2K9</code>",
            )
            return update_id

        token = parts[1].strip().upper()
        result = activate_subscription(token, chat_id, username)

        if result is None and not token.startswith("SUB-"):
            result = activate_subscription(f"SUB-{token}", chat_id, username)

        if result:
            msg_text = (
                f"✅ <b>Iscrizione completata con successo!</b>\n\n"
                f"📍 Comune: <b>{result['comune']}</b> ({result['provincia']})\n"
                f"🗺️ Zona allerta: <b>{result['zona_codice']}</b>\n\n"
                f"Riceverai notifiche quando nella tua zona verrà emessa "
                f"un'allerta meteo.\n"
                f"Per cancellarti usa /cancella."
            )
            send_message(chat_id, msg_text)
            log(f"Iscrizione attivata: {chat_id} (@{username}) → "
                f"{result['comune']} ({result['zona_codice']})")
        else:
            subs = get_user_subscriptions(chat_id)
            if subs:
                lines = [f"ℹ️ <b>Hai già {len(subs)} iscrizioni attive:</b>"]
                for i, s in enumerate(subs, 1):
                    lines.append(
                        f"{i}. {s['comune']} ({s['provincia']}) — zona {s['zona_codice']}"
                    )
                lines.append(
                    "\nIl codice che hai inserito non è più valido (già usato o scaduto)."
                )
                lines.append(
                    "Generane uno nuovo dalla pagina di iscrizione del sito"
                )
                send_message(chat_id, "\n".join(lines))
                log(f"Già iscritto: {chat_id} (@{username}) con {len(subs)} iscrizioni")
            else:
                msg_text = (
                    "❌ <b>Codice non valido o scaduto.</b>\n\n"
                    "Torna sulla pagina di iscrizione del sito\n"
                    "e genera un nuovo codice di iscrizione.\n\n"
                    "I codici scadono dopo 24 ore."
                )
                send_message(chat_id, msg_text)
                log(f"Tentativo fallito: {chat_id} (@{username}) con token {token}")

        return update_id

    # /mio_comune
    if text.startswith("/mio_comune"):
        subs = get_user_subscriptions(chat_id)
        if not subs:
            send_message(chat_id, "❌ Non hai iscrizioni attive. Usa /start per le istruzioni.")
        else:
            lines = [f"📍 Hai <b>{len(subs)}</b> iscrizioni:"]
            for i, s in enumerate(subs, 1):
                lines.append(f"{i}. {s['comune']} ({s['provincia']}) — zona {s['zona_codice']}")
            send_message(chat_id, "\n".join(lines))
        return update_id

    # /liste
    if text.startswith("/liste"):
        subs = get_user_subscriptions(chat_id)
        if not subs:
            send_message(chat_id, "❌ Nessuna iscrizione attiva.")
        else:
            lines = [f"📋 <b>Le tue iscrizioni ({len(subs)}):</b>"]
            for i, s in enumerate(subs, 1):
                lines.append(f"{i}. {s['comune']} ({s['provincia']}) — zona {s['zona_codice']}")
            lines.append("\nPer cancellarne una: <code>/cancella NUMERO</code>")
            send_message(chat_id, "\n".join(lines))
        return update_id

    # /cancella_tutto (DEVE STARE PRIMA DI /cancella per startswith)
    if text.startswith("/cancella_tutto"):
        count = remove_all_subscriptions(chat_id)
        if count > 0:
            send_message(chat_id, f"✅ Cancellate <b>{count}</b> iscrizioni.")
            log(f"Tutte le iscrizioni cancellate: {chat_id} (@{username}) ({count})")
        else:
            send_message(chat_id, "❌ Non hai iscrizioni attive.")
        return update_id

    # /cancella
    if text.startswith("/cancella"):
        parts = text.split()
        subs = get_user_subscriptions(chat_id)

        if not subs:
            send_message(chat_id, "❌ Non hai iscrizioni attive.")
            return update_id

        if len(parts) >= 2:
            try:
                idx = int(parts[1])
                comune = remove_subscription_by_index(chat_id, idx)
                if comune:
                    send_message(chat_id, f"✅ Iscrizione per <b>{comune}</b> cancellata.")
                    log(f"Iscrizione cancellata: {chat_id} (@{username}) → {comune}")
                else:
                    restanti = get_user_subscriptions(chat_id)
                    send_message(
                        chat_id,
                        f"❌ Numero non valido. Hai {len(restanti)} iscrizioni (usa /liste).",
                    )
            except ValueError:
                send_message(chat_id, "⚠️ Uso: <code>/cancella NUMERO</code> (es. /cancella 2)")
        elif len(subs) == 1:
            comune = remove_subscription_by_index(chat_id, 1)
            send_message(chat_id, f"✅ Iscrizione per <b>{comune}</b> cancellata.")
            log(f"Iscrizione cancellata: {chat_id} (@{username}) → {comune}")
        else:
            lines = [f"📋 Hai {len(subs)} iscrizioni. Quale vuoi cancellare?"]
            for i, s in enumerate(subs, 1):
                lines.append(
                    f"<code>/cancella {i}</code> — {s['comune']} ({s['provincia']})"
                )
            lines.append("<code>/cancella_tutto</code> — Cancella tutte")
            send_message(chat_id, "\n".join(lines))
        return update_id

    # /help
    if text.startswith("/help"):
        help_text = (
            "<b>Comandi disponibili:</b>\n\n"
            "/start — Messaggio di benvenuto e istruzioni\n"
            "/subscribe CODICE — Attiva iscrizione con codice\n"
            "/mio_comune — Mostra le tue iscrizioni\n"
            "/liste — Elenca tutte le iscrizioni\n"
            "/cancella — Cancella l'ultima iscrizione\n"
            "/cancella N — Cancella l'iscrizione numero N\n"
            "/cancella_tutto — Cancella tutte le iscrizioni\n"
            "/help — Questo messaggio"
        )
        send_message(chat_id, help_text)
        return update_id

    # Comando non riconosciuto
    send_message(chat_id, "Comando non riconosciuto. Usa /help per i comandi disponibili.")
    return update_id


# ── Polling ─────────────────────────────────────────────────────────────
def poll_once() -> int:
    offset = get_last_offset()

    try:
        resp = requests.post(
            config.telegram_api_url("getUpdates"),
            json={
                "offset": offset,
                "timeout": 0,
                "allowed_updates": ["message"],
            },
            timeout=config.REQUESTS_TIMEOUT,
        )
        if resp.status_code != 200:
            log(f"Errore getUpdates: {resp.status_code}")
            return 0

        updates = resp.json().get("result", [])
        if not updates:
            return 0

        last_id = offset
        for update in updates:
            uid = process_update(update)
            if uid and uid > last_id:
                last_id = uid

        if last_id > offset:
            save_last_offset(last_id)

        cleaned = cleanup_expired()
        if cleaned > 0:
            log(f"Puliti {cleaned} token pending scaduti.")

        return len(updates)

    except requests.RequestException as e:
        log(f"Errore polling: {e}")
        return 0


def poll_daemon():
    log("Avviato bot listener in modalità demone.")
    while True:
        try:
            poll_once()
        except Exception as e:
            log(f"Errore nel ciclo demone: {e}")
        time.sleep(5)


# ── Lock file ───────────────────────────────────────────────────────────
def acquire_lock():
    """Acquisisce un lock file. Restituisce file descriptor o None."""
    try:
        import fcntl
        lock_fd = open(config.BOT_LOCK_FILE, "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
        return lock_fd
    except (IOError, BlockingIOError):
        return None
    except ImportError:
        return True  # fcntl non disponibile (Windows)


# ── Entry point ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    config.ensure_dirs()

    lock_fd = acquire_lock()
    if lock_fd is None:
        log("Un'altra istanza è già in esecuzione. Skip.")
        sys.exit(0)

    try:
        if "--daemon" in sys.argv:
            poll_daemon()
        else:
            count = poll_once()
            if count > 0:
                log(f"Processati {count} update(s).")
    finally:
        if lock_fd is not None and lock_fd is not True:
            try:
                import fcntl
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                lock_fd.close()
                os.unlink(config.BOT_LOCK_FILE)
            except Exception:
                pass
