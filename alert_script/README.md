# Allerta Meteo

Sistema per il monitoraggio e la notifica delle allerte meteorologiche della Protezione Civile Nazionale.

## Architettura

Il sistema e' composto da 5 moduli che lavorano insieme:

| Modulo | Ruolo |
|--------|-------|
| `script.py` | Scarica i bollettini dalla Protezione Civile Nazionale, genera i dati, invia notifiche broadcast e individuali via Telegram, genera la pagina HTML |
| `script_cfd.py` | Monitora il portale CFD per nuovi avvisi AAR/AVM e li invia via Telegram |
| `api_server.py` | Server HTTP per la generazione di token di iscrizione (POST /alert/api/subscribe) |
| `bot_listener.py` | Listener Telegram che elabora i comandi utente (/subscribe, /cancella, /liste, etc.) |
| `subscriptions.py` | Libreria per la gestione delle iscrizioni (multi-utente, multi-comune) |

## Flusso di notifica

1. `script.py` scarica gli shapefile dal repository DPC (Protezione Civile Nazionale)
2. Estrae i dati di criticita per zona e comune, genera CSV/GeoJSON
3. Calcola un fingerprint SHA256 strutturale dei dati di allerta
4. Se il fingerprint e' cambiato:
   - Invia un **broadcast riepilogativo** al canale Telegram (una sola volta per bollettino)
   - Invia **notifiche individuali** a tutti gli iscritti alla zona interessata
5. Il tracking delle notifiche gia' inviate e' in `sent_notifications.json`

## Installazione

### Prerequisiti

- Python 3.10+
- pip
- Un bot Telegram (crealo tramite @BotFather)
- Un gruppo/canale Telegram e il suo chat_id (lo ottieni inviando un messaggio al bot e leggendo /getUpdates)

### Passi

```bash
# 1. Clona il repository
git clone https://github.com/ravem/AllertaMeteo.git
cd AllertaMeteo

# 2. Crea il file .env con i dati del tuo bot Telegram
cp .env.example .env
```

Modifica `.env` con i valori reali:

```
TELEGRAM_TOKEN="il_token_del_tuo_bot"
TELEGRAM_CHAT_ID="id_del_tuo_gruppo"
```

```bash
# 3. Installa le dipendenze
pip install -r requirements.txt

# 4. Esegui lo script principale per un primo test
python3 script.py

# 5. (Opzionale) Avvia il server API per le iscrizioni
python3 api_server.py

# 6. (Opzionale) Avvia il bot listener per i comandi Telegram
python3 bot_listener.py --daemon
```

### Configurazione systemd (server production)

```bash
cp systemd/alert-api.service.template /etc/systemd/system/alert-api.service
cp systemd/alert-bot.service.template /etc/systemd/system/alert-bot.service
```

Modifica i file in `/etc/systemd/system/` con:
- `User=IL_TUO_USER` con il tuo username
- `/percorso/del/progetto` con il percorso reale

Poi:

```bash
systemctl daemon-reload
systemctl enable alert-api alert-bot
systemctl start alert-api alert-bot
```

### Configurazione Nginx (opzionale)

Per esporre l'API di iscrizione tramite Nginx:

```nginx
location /alert/api/ {
    proxy_pass http://127.0.0.1:8081/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

### Esecuzione periodica via cron (opzionale)

```cron
# Due volte al giorno (7:30 e 14:30)
30 7,14 * * * cd /percorso/AllertaMeteo && /usr/bin/python3 script.py

# Ogni 30 minuti nelle ore diurne per il monitoraggio CFD
*/30 7-20 * * * cd /percorso/AllertaMeteo && /usr/bin/python3 script_cfd.py
```

## Variabili d'ambiente

| Variabile | Obbligatoria | Default | Descrizione |
|-----------|-------------|---------|-------------|
| TELEGRAM_TOKEN | Si | - | Token del bot Telegram |
| TELEGRAM_CHAT_ID | Si | - | Chat ID del gruppo/canale |
| ALERT_HTML_PATH | No | ../web/alert/index.html | Path per la pagina HTML generata |

## Struttura del progetto

```
AllertaMeteo/
├── config.py                # Configurazione centralizzata
├── script.py                # Script principale: ingestione e notifiche
├── script_cfd.py            # Monitoraggio avvisi CFD (AAR/AVM)
├── bot_listener.py          # Listener comandi Telegram
├── api_server.py            # Server HTTP API iscrizioni
├── subscriptions.py         # Libreria gestione iscrizioni
├── subscribe_api.py         # Versione CGI dell'API (per hosting condiviso)
├── systemd/                 # Template servizi systemd
├── requirements.txt         # Dipendenze Python
├── .env.example             # Template variabili d'ambiente
├── .gitignore
├── data/                    # Dati generati (in .gitignore)
│   ├── bollettini/          # CSV bollettini per zona e comune
│   └── zone/                # GeoJSON/CSV delle zone di allerta
├── cfd/                     # PDF degli avvisi scaricati (in .gitignore)
└── web/                     # Frontend web
    └── alert/
        ├── index.html
        └── subscription.html
```

## Modifiche principali rispetto alla versione originale

- **config.py**: path calcolati dinamicamente, token da variabili d'ambiente, non hardcoded
- **Fingerprint SHA256**: evita notifiche duplicate anche se la data di pubblicazione cambia (basta che i dati di allerta siano invariati)
- **subprocess.run()**: sostituisce os.system() per maggiore sicurezza
- **Multi-iscrizione**: un utente puo' iscriversi a piu' comuni contemporaneamente
- **Antispam**: honeypot + captcha nell'API di iscrizione
- **Pulizia log**: troncamento automatico dei log oltre 1MB
- **Lock file**: evita esecuzioni concorrenti del bot listener
- **sent_notifications.json**: tracking persistente delle notifiche gia' inviate
