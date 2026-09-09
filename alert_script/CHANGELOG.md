# Changelog

## 2026-09-09 — script.py ricostruito e repository ripulito

### Modifiche principali

1. **script.py** — Ricostruito da zero (era vuoto, 0 byte)
   - Fase 1: download zip dal DPC, estrazione shapefile, generazione CSV
   - Fase 2: caricamento dati, fingerprint, broadcast notifiche via subscriptions
   - Generazione alert.txt e HTML
   - Tracking notifiche in sent_notifications.json

2. **config.py** — Rimosso warning per CHAT_ID (non più richiesto, si usa subscriptions)

3. **requirements.txt** — Riempito con dipendenze necessarie
   (geopandas, pandas, requests, python-dotenv)

### Fix (testati)

- **Bug _trova_zone_allertate**: usava `k in [lista]` invece di `k in stringa` — nessuna allerta veniva mai trovata
- **Bug _build_column_map**: i nomi reali DBF sono `Zona_all`, `Nome_zona`, `Criticita`, `Idrogeo`, `Temporali`, `Idraulico` (non nomi standard)
- **Mancanza date**: lo shapefile DPC non ha colonne data; estratte dal nome file (`YYYYMMDD_HHMM`)
- **Aggiunto zona_nome** in COLONNE_ZONE e COLONNE_COMUNI (veniva perso)
- **Join spaziale**: generazione CSV comuni via sjoin tra punti comuni italiani e poligoni zone
- **Bug alerta_info.get**: None non attiva il default, fix con `(x or {})`

### Risultato test

- Download DPC e generazione CSV: OK (187 zone, ~7900 comuni)
- Rilevamento allerte: OK (50 oggi + 91 domani = 115 zone uniche)
- Broadcast a iscritti: OK (5 notifiche tentate, bloccate da TOKEN assente)
- Generazione HTML: OK

### Pulizia

- Rimossi: OldScripts/ (versione vecchia con TOKEN hardcoded)
- Rimossi: archive/ (copia speculare di OldScripts/)
- Rimossi: __pycache__/
- Rimossi: log e file temporanei non più necessari
- Rimossi: PDF CFD vecchi (tenuti solo ultimi 2 per tipo)
- Tenuti: subscriptions.json, bot_listener.py, api_server.py, script_cfd.py, config.py

### CFD aggiornato (script_cfd.py + config.py)
- URL CFD cambiate: ora formato diretto `{base_url}/{PREFIX}_{YYMMDD}_CFD.pdf`
- Nuovi prefissi: BVM e BAR (erano AAR e AVM)
- Ricerca PDF: prova oggi, ieri, fino a 7 giorni indietro
- Destinatario configurabile via `CFD_CHAT_ID` in .env / config.py
- Fix: bug `r.content` già consumato dopo `iter_content`
- Fix: virgolette nel .env che rompevano l'URL dell'API Telegram

### Test finale
- 4 PDF CFD scaricati e inviati con successo a ravem ✅
- Script allerta meteo funzionante (4 messaggi inviati) ✅

### File backup

- `alert_script-backup-20260909-075558.tgz` — backup pre-modifiche
- `alert_script-dopo-pulizia-20260909-083020.tgz` — backup dopo pulizia
- `alert_script-dopo-test-20260909-083758.tgz` — backup dopo test funzionante
- `alert_script-finale-20260909-085733.tgz` — backup finale pronto per il server
