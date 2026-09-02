#!/usr/bin/env python3
"""
Mini server HTTP per le API di iscrizione allerte meteo.
Nginx fa da proxy: /alert/api/* → http://127.0.0.1:8081/*

Avvio:
  python3 api_server.py              # primo piano
  python3 api_server.py --daemon &   # background (fork)
"""

import sys
import os
import json
import http.server
import urllib.parse

import config
from subscriptions import generate_token

HOST = "127.0.0.1"
PORT = 8081


class SubscriptionHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        """Override per loggare su file."""
        timestamp = self.date_time_string()
        msg = f"[{timestamp}] {args[0]} {args[1]} {args[2]}"
        try:
            with open(config.API_SERVER_LOG, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass

    def _send_json(self, status_code, data):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/alert/api/subscribe":
            self._handle_subscribe()
        else:
            self._send_json(404, {"status": "error", "message": "Endpoint non trovato"})

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/alert/api/health":
            self._send_json(200, {"status": "ok", "service": "allerta-meteo-api"})
        else:
            self._send_json(404, {"status": "error", "message": "Endpoint non trovato"})

    def _handle_subscribe(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self._send_json(400, {"status": "error", "message": "Richiesta vuota."})
                return

            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)
        except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
            self._send_json(400, {"status": "error", "message": "JSON non valido."})
            return

        # Honeypot antispam (campo invisibile per bot)
        hp = data.get("hp", "")
        if hp:
            self._send_json(403, {"status": "error", "message": "Richiesta rifiutata."})
            return

        # Captcha antispam
        captcha = data.get("captcha")
        if not isinstance(captcha, int) or captcha < 1 or captcha > 99:
            self._send_json(
                400,
                {"status": "error", "message": "Verifica antispam fallita. Ricarica la pagina."},
            )
            return

        required = ["comune", "provincia", "regione", "zona_codice", "zona_nome"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            self._send_json(
                400,
                {"status": "error", "message": f"Campi mancanti: {', '.join(missing)}"},
            )
            return

        try:
            token = generate_token(
                comune=data["comune"],
                provincia=data["provincia"],
                regione=data["regione"],
                zona_codice=data["zona_codice"],
                zona_nome=data["zona_nome"],
            )
            self._send_json(
                200,
                {
                    "status": "ok",
                    "token": token,
                    "message": "Codice generato con successo.",
                },
            )
        except Exception as e:
            self._send_json(
                500, {"status": "error", "message": f"Errore interno: {e}"}
            )


def main():
    try:
        server = http.server.HTTPServer((HOST, PORT), SubscriptionHandler)
    except OSError as e:
        if e.errno == 98:  # Address already in use
            sys.exit(0)
        else:
            print(f"Errore avvio server: {e}")
            sys.exit(1)

    config.ensure_dirs()

    print(f"✅ API server in ascolto su http://{HOST}:{PORT}")
    print(f"   Endpoint: POST /alert/api/subscribe")
    print(f"   Health:   GET  /alert/api/health")
    print()

    if "--daemon" in sys.argv:
        pid = os.fork()
        if pid > 0:
            print(f"   PID: {pid}")
            sys.exit(0)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer fermato.")
        server.server_close()


if __name__ == "__main__":
    main()
