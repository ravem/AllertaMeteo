#!/usr/bin/env python3
"""
API per iscrizione allerte meteo (CGI).
Riceve POST con JSON {comune, provincia, regione, zona_codice, zona_nome}
Restituisce JSON con token.

Posizionare in /usr/lib/cgi-bin/subscribe_api.py
oppure /var/www/init5.it/cgi-bin/subscribe_api.py
"""

import sys
import json
import os

# Assicura che il path delle subscriptions sia trovabile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from subscriptions import generate_token

def respond(status, data):
    """Invia risposta JSON."""
    content = json.dumps(data, ensure_ascii=False)
    print(f"Content-Type: application/json; charset=utf-8")
    print(f"Access-Control-Allow-Origin: *")
    print(f"Content-Length: {len(content.encode('utf-8'))}")
    print()
    print(content)
    sys.exit(0)


def respond_error(msg, code=400):
    respond(code, {"status": "error", "message": msg})


# Leggi il body POST
try:
    content_length = int(os.environ.get("CONTENT_LENGTH", 0))
    if content_length == 0:
        respond_error("Richiesta vuota. Inviare un JSON con comune, provincia, regione, zona_codice, zona_nome.")
    
    body = sys.stdin.buffer.read(content_length).decode("utf-8")
    data = json.loads(body)
except (json.JSONDecodeError, ValueError, KeyError):
    respond_error("Formato JSON non valido.")

# Validazione campi richiesti
required = ["comune", "provincia", "regione", "zona_codice", "zona_nome"]
missing = [f for f in required if not data.get(f)]
if missing:
    respond_error(f"Campi mancanti: {', '.join(missing)}")

try:
    token = generate_token(
        comune=data["comune"],
        provincia=data["provincia"],
        regione=data["regione"],
        zona_codice=data["zona_codice"],
        zona_nome=data["zona_nome"],
    )
    respond(200, {"status": "ok", "token": token, "message": "Codice generato con successo."})
except Exception as e:
    respond_error(f"Errore interno: {e}", 500)
