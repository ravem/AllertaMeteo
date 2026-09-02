import os
import shutil
import logging
from datetime import datetime
import pandas as pd
import requests
import filecmp

# Configurazione logging (sovrascrive il file ad ogni esecuzione)
logging.basicConfig(
    filename="/home/paolo/alert/alert.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode='w'  # sovrascrive ogni volta
)

# Percorsi
base_dir = "/home/paolo/alert"
data_dir = os.path.join(base_dir, "data", "bollettini")
lastrun_path = os.path.join(base_dir, "lastrun.txt")
alert_path = os.path.join(base_dir, "alert.txt")
alert_old_path = os.path.join(base_dir, "alert_old.txt")
send_log_path = os.path.join(base_dir, "send_message.log")
html_path = "/var/www/init5.it/html/alert/index.html"

# Telegram
TOKEN="6210624308:AAHUpRt8Xgb_s_3qkDR4NPXkRjADqLlwPGk"
CHAT_ID = "-1001978022892"

# Scarica i file
files = {
    "bollettino-oggi-zone-latest.csv": "https://raw.githubusercontent.com/opendatasicilia/DPC-bollettini-criticita-idrogeologica-idraulica/main/data/bollettini/bollettino-oggi-zone-latest.csv",
    "bollettino-domani-zone-latest.csv": "https://raw.githubusercontent.com/opendatasicilia/DPC-bollettini-criticita-idrogeologica-idraulica/main/data/bollettini/bollettino-domani-zone-latest.csv",
    "bollettino-oggi-comuni-latest.csv": "https://raw.githubusercontent.com/opendatasicilia/DPC-bollettini-criticita-idrogeologica-idraulica/main/data/bollettini/bollettino-oggi-comuni-latest.csv",
    "bollettino-domani-comuni-latest.csv": "https://raw.githubusercontent.com/opendatasicilia/DPC-bollettini-criticita-idrogeologica-idraulica/main/data/bollettini/bollettino-domani-comuni-latest.csv",
}

os.makedirs(data_dir, exist_ok=True)
for fname, url in files.items():
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        with open(os.path.join(data_dir, fname), "wb") as f:
            f.write(resp.content)
        logging.info(f"Scaricato {fname}")
    except Exception as e:
        logging.error(f"Errore scaricando {fname}: {e}")

# Timestamp
with open(lastrun_path, "w") as f:
    f.write("Ultimo controllo eseguito il " + datetime.now().strftime("%d/%m/%Y %T") + "\n")

# Ruota alert_old
if os.path.exists(alert_path):
    shutil.copy(alert_path, alert_old_path)
    logging.info("Rotated alert.txt to alert_old.txt")

# Funzioni di estrazione con emoji

def estrai_zona(df, zona="Vene-E"):
    lines = []
    sel = df[df.iloc[:, 3] == zona]
    for _, r in sel.iterrows():
        criticita_std = str(r[4]).upper()
        emoji = ""
        colore = ""
        if "NESSUNA" in criticita_std:
            colore = "green"
            emoji = "🟢"
            criticita_std = "NESSUNA ALLERTA"
        elif "GIALLA" in criticita_std:
            colore = "#CCCC00"
            emoji = "🟡"
            criticita_std = "ALLERTA GIALLA"
        elif "ARANCIONE" in criticita_std:
            colore = "orange"
            emoji = "🟠"
            criticita_std = "ALLERTA ARANCIONE"
        elif "ROSSA" in criticita_std:
            colore = "red"
            emoji = "🔴"
            criticita_std = "ALLERTA ROSSA"

        if colore:
            lines.append(f"{emoji} Zona {zona}\n"
                         f"Bollettino emesso il {r[0][8:10]}/{r[0][5:7]}/{r[0][0:4]} alle ore {r[0][11:19]}\n"
                         f"Inizio validità: {r[1][8:10]}/{r[1][5:7]}/{r[1][0:4]} alle ore {r[1][11:19]}\n"
                         f"Termine validità: {r[2][8:10]}/{r[2][5:7]}/{r[2][0:4]} alle ore {r[2][11:19]}\n"
                         f"{criticita_std}\n\n")
    return "".join(lines)

def estrai_comune(df, comune="Saonara"):
    lines = []
    sel = df[df.iloc[:, 4] == comune]
    for _, r in sel.iterrows():
        criticita_std = str(r[8]).upper()
        emoji = ""
        colore = ""
        if "NESSUNA" in criticita_std:
            colore = "green"
            emoji = "🟢"
            criticita_std = "NESSUNA ALLERTA"
        elif "GIALLA" in criticita_std:
            colore = "#CCCC00"
            emoji = "🟡"
            criticita_std = "ALLERTA GIALLA"
        elif "ARANCIONE" in criticita_std:
            colore = "orange"
            emoji = "🟠"
            criticita_std = "ALLERTA ARANCIONE"
        elif "ROSSA" in criticita_std:
            colore = "red"
            emoji = "🔴"
            criticita_std = "ALLERTA ROSSA"

        if colore:
            lines.append(f"{emoji} Comune di {comune}\n"
                         f"Bollettino emesso il {r[0][8:10]}/{r[0][5:7]}/{r[0][0:4]} alle ore {r[0][11:19]}\n"
                         f"Inizio validità: {r[1][8:10]}/{r[1][5:7]}/{r[1][0:4]} alle ore {r[1][11:19]}\n"
                         f"Termine validità: {r[2][8:10]}/{r[2][5:7]}/{r[2][0:4]} alle ore {r[2][11:19]}\n"
                         f"{criticita_std}\n\n")
    return "".join(lines)

# Estrai per oggi e domani
zone_oggi = estrai_zona(pd.read_csv(os.path.join(data_dir, "bollettino-oggi-zone-latest.csv")))
zone_domani = estrai_zona(pd.read_csv(os.path.join(data_dir, "bollettino-domani-zone-latest.csv")))
comune_oggi = estrai_comune(pd.read_csv(os.path.join(data_dir, "bollettino-oggi-comuni-latest.csv")))
comune_domani = estrai_comune(pd.read_csv(os.path.join(data_dir, "bollettino-domani-comuni-latest.csv")))

# Unisci in alert.txt (solo testo semplice per Telegram)
def testo_senza_html(s):
    import re
    return re.sub(r'<[^>]*>', '', s)

msg_content = testo_senza_html(zone_oggi + zone_domani + comune_oggi + comune_domani)
with open(alert_path, "w") as out:
    out.write(msg_content)
logging.info("Generato alert.txt unificando i bollettini rilevanti")

# Invia messaggio Telegram se cambiato e contiene GIALLA/ARANCIONE/ROSSA
changed = not os.path.exists(alert_old_path) or not filecmp.cmp(alert_path, alert_old_path, shallow=False)
if changed and any(k in msg_content.upper() for k in ["GIALLA", "ARANCIONE", "ROSSA"]):
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg_content, "parse_mode": "Markdown"}
        )
        logging.info(f"Telegram inviato, status {resp.status_code}")
        with open(send_log_path, "w") as slog:
            slog.write(f"Status: {resp.status_code}\nResponse: {resp.text}\n")
        resp.raise_for_status()
    except Exception as e:
        logging.error(f"Errore invio Telegram: {e}")

# Genera HTML (font Roboto senza <pre>), titolo h2 senza margini/padding
header = (
    '<!DOCTYPE html><html><head><meta charset="UTF-8">'
    '<title>Allerta meteo</title>'
    '<link href="https://fonts.googleapis.com/css2?family=Roboto&display=swap" rel="stylesheet">'
    '<style>'
    'body{font-family:"Roboto",sans-serif; font-size:1em; white-space: pre-wrap;}'
    'h2 { margin: 0; padding: 0; }'
    '.alert-green { color: green; }'
    '.alert-yellow { color: #CCCC00; }'
    '.alert-orange { color: orange; }'
    '.alert-red { color: red; }'
    '</style>'
    '</head><body>'
)

footer = '</body></html>'

# Per la pagina HTML aggiungiamo la colorazione delle righe di allerta e rimozione di "TIPOLOGIA ALLERTA:" e "Assenza di fenomeni significativi prevedibili"
def pulisci_per_html(testo):
    import re
    testo = testo.replace("TIPOLOGIA ALLERTA:", "")
    testo = re.sub(r"Assenza di fenomeni significativi prevedibili\s*/\s*", "", testo)
    return testo.strip()

def color_alert_html(testo):
    # Applica il colore alle linee che contengono l’allerta
    import re
    def replacer(match):
        line = match.group(0)
        if "NESSUNA ALLERTA" in line:
            return f'<span class="alert-green">{line}</span>'
        elif "ALLERTA GIALLA" in line:
            return f'<span class="alert-yellow">{line}</span>'
        elif "ALLERTA ARANCIONE" in line:
            return f'<span class="alert-orange">{line}</span>'
        elif "ALLERTA ROSSA" in line:
            return f'<span class="alert-red">{line}</span>'
        else:
            return line

    # Coloriamo le righe che contengono i tipi di allerta
    return re.sub(r'.*ALLERTA.*|.*NESSUNA ALLERTA.*', replacer, testo)

html_content = pulisci_per_html(zone_oggi + zone_domani + comune_oggi + comune_domani)
html_content = color_alert_html(html_content)

with open(html_path, "w") as html:
    html.write(header)
    html.write(open(lastrun_path).read() + "\n\n")
    html.write(html_content + "\n")
    html.write(footer)

logging.info("Generato HTML finale")
