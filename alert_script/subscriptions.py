"""
Gestione iscrizioni allerte meteo.
Supporta MULTIPLE iscrizioni per utente.
Legge e scrive subscriptions.json condiviso tra API e bot.
"""

import json
import os
import secrets
import string
from datetime import datetime, timedelta

# Percorso del file iscrizioni (sul server)
SUBSCRIPTIONS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "subscriptions.json")


def _load():
    """Carica il database iscrizioni."""
    if os.path.exists(SUBSCRIPTIONS_PATH):
        try:
            with open(SUBSCRIPTIONS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"pending": {}, "active": {}}


def _save(data):
    """Salva il database iscrizioni atomically."""
    tmp = SUBSCRIPTIONS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, SUBSCRIPTIONS_PATH)


def _gen_id():
    """Genera un ID univoco per una subscription."""
    return "s_" + "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))


def generate_token(comune, provincia, regione, zona_codice, zona_nome):
    """
    Genera un token univoco e salva la richiesta pending.
    Restituisce il token.
    """
    data = _load()

    alphabet = string.ascii_uppercase + string.digits
    token = "SUB-" + "".join(secrets.choice(alphabet) for _ in range(6))
    while token in data["pending"]:
        token = "SUB-" + "".join(secrets.choice(alphabet) for _ in range(6))

    data["pending"][token] = {
        "comune": comune,
        "provincia": provincia,
        "regione": regione,
        "zona_codice": zona_codice,
        "zona_nome": zona_nome,
        "created_at": datetime.now().isoformat(),
        "expires_at": (datetime.now() + timedelta(hours=24)).isoformat(),
    }

    _save(data)
    return token


def activate_subscription(token, chat_id, username=""):
    """
    Attiva un'iscrizione pending: sposta da pending ad active.
    Un utente può avere MULTIPLE iscrizioni (es. casa + lavoro).
    Restituisce il dict dell'iscrizione attivata o None se token non valido/scaduto.
    """
    data = _load()

    if token not in data["pending"]:
        return None

    pending = data["pending"][token]

    # Verifica scadenza
    expires = datetime.fromisoformat(pending["expires_at"])
    if datetime.now() > expires:
        del data["pending"][token]
        _save(data)
        return None

    # Costruisce la nuova iscrizione
    subscription = {
        "id": _gen_id(),
        "chat_id": chat_id,
        "username": username,
        "comune": pending["comune"],
        "provincia": pending["provincia"],
        "regione": pending["regione"],
        "zona_codice": pending["zona_codice"],
        "zona_nome": pending["zona_nome"],
        "subscribed_at": datetime.now().isoformat(),
    }

    # Aggiunge alla lista dell'utente (creandola se prima non c'era)
    key = str(chat_id)
    if key not in data["active"]:
        data["active"][key] = []
    data["active"][key].append(subscription)
    del data["pending"][token]
    _save(data)

    return subscription


def get_user_subscriptions(chat_id):
    """Restituisce tutte le iscrizioni di un utente. Lista (anche vuota)."""
    data = _load()
    return data.get("active", {}).get(str(chat_id), [])


def get_subscriptions_by_zone(zona_codice):
    """
    Restituisce tutte le iscrizioni attive per una data zona.
    Lista di dict con chat_id, comune, provincia, username.
    Se una subscription manca del campo 'id' (vecchio formato),
    viene saltata e loggata, senza far crashare lo script.
    """
    data = _load()
    results = []
    for subs in data.get("active", {}).values():
        for sub in subs:
            if sub.get("zona_codice") == zona_codice:
                # Gestione retrocompatibile: se manca 'id' lo generiamo al volo
                if "id" not in sub:
                    sub["id"] = _gen_id()
                    # Salviamo subito per persistenza
                    _save(data)
                results.append({
                    "id": sub["id"],
                    "chat_id": sub.get("chat_id"),
                    "username": sub.get("username", ""),
                    "comune": sub.get("comune", "?"),
                    "provincia": sub.get("provincia", "?"),
                    "regione": sub.get("regione", ""),
                    "zona_nome": sub.get("zona_nome", "?"),
                })
    return results


def get_all_active():
    """Restituisce tutte le iscrizioni attive (lista piatta)."""
    data = _load()
    all_subs = []
    for subs in data.get("active", {}).values():
        all_subs.extend(subs)
    return all_subs


def remove_subscription_by_id(chat_id, sub_id):
    """
    Rimuove una specifica iscrizione di un utente.
    Restituisce True se trovata e rimossa, False altrimenti.
    """
    data = _load()
    key = str(chat_id)
    subs = data.get("active", {}).get(key, [])
    for i, sub in enumerate(subs):
        if sub["id"] == sub_id:
            del subs[i]
            if not subs:
                del data["active"][key]
            _save(data)
            return True
    return False


def remove_subscription_by_index(chat_id, index):
    """
    Rimuove un'iscrizione per indice (1-based, come mostrato all'utente).
    Restituisce il nome del comune rimosso, o None se indice non valido.
    """
    data = _load()
    key = str(chat_id)
    subs = data.get("active", {}).get(key, [])
    if 1 <= index <= len(subs):
        sub = subs[index - 1]
        comune = sub["comune"]
        del subs[index - 1]
        if not subs:
            del data["active"][key]
        _save(data)
        return comune
    return None


def remove_all_subscriptions(chat_id):
    """Rimuove TUTTE le iscrizioni di un utente. Restituisce il numero rimosse."""
    data = _load()
    key = str(chat_id)
    subs = data.get("active", {}).get(key, [])
    count = len(subs)
    if count > 0:
        del data["active"][key]
        _save(data)
    return count


def cleanup_expired():
    """Rimuove i token pending scaduti."""
    data = _load()
    now = datetime.now()
    expired = [t for t, p in data["pending"].items()
               if datetime.fromisoformat(p["expires_at"]) < now]
    for t in expired:
        del data["pending"][t]
    if expired:
        _save(data)
    return len(expired)
