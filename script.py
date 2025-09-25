import os
import pandas as pd
import geopandas as gpd
import re
import glob
from datetime import datetime
from datetime import timedelta
import filecmp
import logging
from zoneinfo import ZoneInfo
import requests
import shutil

import warnings
warnings.filterwarnings("ignore")

'''
    Task 1: creare dump delle zone
    Task 2: creare dump dei bollettini per zona
    Task 3: creare dump dei bollettini per comune
'''

ROOT_DIR = os.getcwd()
TMP_DIR=os.path.join(ROOT_DIR,'tmp')
DATA_DIR = os.path.join(ROOT_DIR,'/home/user/alert/data')
BOLLETTINI_DIR = os.path.join(DATA_DIR,'bollettini')
ZONE_DIR = os.path.join(DATA_DIR,'zone')


if os.path.exists(TMP_DIR):
    print("Cancello directory tmp")
    shutil.rmtree(TMP_DIR)    
print("Creo directory tmp")    
os.mkdir(TMP_DIR)

if os.path.exists(DATA_DIR):
    print("Cancello directory data")
    shutil.rmtree(DATA_DIR)    
print("Creo directory data")
os.mkdir(DATA_DIR)
print("Credo directory data/bollettini")
os.mkdir(BOLLETTINI_DIR)
print("Creo directory data/zone")
os.mkdir(ZONE_DIR)

PROTEZIONE_CIVILE_BOLLETTINI_URL = 'https://github.com/pcm-dpc/DPC-Bollettini-Criticita-Idrogeologica-Idraulica/blob/master/files/all/latest_all.zip?raw=true'
COMUNI_ITALIANI_URL = 'https://raw.githubusercontent.com/opendatasicilia/comuni-italiani/main/dati/main.csv'

print('Downloading dati criticità, idrogeologica, idraulica, temporali della Protezione Civile')

try:
    r = requests.get(PROTEZIONE_CIVILE_BOLLETTINI_URL)
except Exception as e:
    os.sys.exit(f"Richiesta URL {PROTEZIONE_CIVILE_BOLLETTINI_URL} non andata a buon fine")


if r.status_code!=200:
    os.sys.exit(f"Status code dell'URL {PROTEZIONE_CIVILE_BOLLETTINI_URL} diverso da 200")

latest_file = f"{TMP_DIR}{os.sep}latest_all.zip"
with open(latest_file, 'wb') as code:
    code.write(r.content)

print("Unzippo i dati scaricati")
os.system(f"unzip {latest_file} -d {TMP_DIR}")

shapefiles = glob.glob(f"{TMP_DIR}{os.sep}*.shp")

# Step 1 - Dump zone
print("Sto creando il dump delle zone")
zone_df = gpd.read_file(shapefiles[0])

(zone_df
    .loc[:,['Zona_all','Nome_zona','geometry']]
    .rename(columns={'Zona_all':'zona_codice','Nome_zona':'zona_nome'})
    .to_file(f"{ZONE_DIR}{os.sep}zone.geojson", driver='GeoJSON') 
)

(zone_df
    .loc[:,['Zona_all','Nome_zona']]
    .rename(columns={'Zona_all':'zona_codice','Nome_zona':'zona_nome'})
    .loc[:,['zona_codice','zona_nome']]
    .to_csv(f"{ZONE_DIR}{os.sep}zone.csv",index=False)
)

matched = re.search('.*tmp/(\d{8})_(\d{4})_.*', shapefiles[0],re.MULTILINE|re.DOTALL)

if not matched:
    os.sys.exit("Errore nell'estrazione data/ora di pubblicazione dal nome del file")


today_gr = matched.group(1)
hours_minutes = matched.group(2)
hours = int(hours_minutes[0:2])
minutes = int(hours_minutes[2:4])
today_dt = datetime.strptime(today_gr, '%Y%m%d').replace(tzinfo=ZoneInfo('Europe/Rome'))
tomorrow_dt = today_dt + timedelta(days=1)
today_start_dt =  today_dt.replace(hour=hours, minute=minutes)
today_str=today_dt.strftime("%Y%m%d")
tomorrow_str=tomorrow_dt.strftime("%Y%m%d")
data_pubblicazione = today_dt.replace(hour=hours, minute=minutes, second=59).isoformat()


comuni_df = pd.read_csv(COMUNI_ITALIANI_URL, converters={'pro_com_t': str})
comuni_gdf = gpd.GeoDataFrame(comuni_df, geometry=gpd.points_from_xy(comuni_df.long, comuni_df.lat))


when_labels = {'today':'oggi','tomorrow':'domani'}
joined = None

for shapefile in shapefiles:
    print(f"Sto leggendo questo shapefile {shapefile}")
    df = gpd.read_file(shapefile)
    joined = gpd.sjoin(left_df=comuni_gdf, right_df=df, how='left')

    if 'today' in shapefile:
        when = 'today'
        data_validita_inizio = today_dt.replace(hour=hours, minute=minutes, second=59).isoformat()
        data_validita_fine = today_dt.replace(hour=23, minute=59, second=59).isoformat()
        
    elif 'tomorrow' in shapefile:
        when = 'tomorrow'        
        data_validita_inizio = tomorrow_dt.replace(hour=0, minute=0, second=0).isoformat()
        data_validita_fine = tomorrow_dt.replace(hour=23, minute=59, second=59).isoformat()
        

        
    bollettino_avvisi_zone = (df[['Zona_all','Nome_zona','Criticita','Idrogeo','Temporali','Idraulico']]
                            .rename(columns={'Zona_all':'zona_codice','Criticita': 'avviso_criticita','Idrogeo': 'avviso_idrogeologico','Temporali': 'avviso_temporali','Idraulico': 'avviso_idraulico',})
                            .assign(data_pubblicazione=data_pubblicazione)
                            .assign(data_validita_inizio=data_validita_inizio)
                            .assign(data_validita_fine=data_validita_fine)
                            .loc[:, ['data_pubblicazione','data_validita_inizio','data_validita_fine','zona_codice','avviso_criticita','avviso_idrogeologico','avviso_temporali','avviso_idraulico']]
                            )
    #Task1 - backup bollettini zone 
    bollettino_avvisi_zone.to_csv(f"{BOLLETTINI_DIR}{os.sep}{today_str}-bollettino-{when_labels[when]}-zone.csv", index=False)  
    print(f"Bollettino di zona di {when_labels[when]} generato")

    bollettino_avvisi_zone.to_csv(f"{BOLLETTINI_DIR}{os.sep}bollettino-{when_labels[when]}-zone-latest.csv", index=False)      
    print(f"Bollettino di zona di {when_labels[when]} (versione latest) generato")

    bollettino_avvisi_comuni = (joined
                                .rename(columns={'comune':'comune_nome','den_prov':'provincia_nome','den_reg':'regione_nome','Zona_all':'zona_codice','Criticita': 'avviso_criticita','Idrogeo': 'avviso_idrogeologico','Temporali': 'avviso_temporali','Idraulico': 'avviso_idraulico',})
                                .assign(data_pubblicazione=data_pubblicazione)
                                .assign(data_validita_inizio=data_validita_inizio)
                                .assign(data_validita_fine=data_validita_fine)                                        
                                .loc[:, ['data_pubblicazione','data_validita_inizio','data_validita_fine','pro_com_t','comune_nome','provincia_nome','regione_nome','zona_codice','avviso_criticita','avviso_idrogeologico','avviso_temporali','avviso_idraulico']]               
                                )
    #Task2 - backup bollettini comuni 
    bollettino_avvisi_comuni.to_csv(f"{BOLLETTINI_DIR}{os.sep}{today_str}-bollettino-{when_labels[when]}-comuni.csv", index=False)
    print(f"Bollettino comunale di {when_labels[when]} generato")

    bollettino_avvisi_comuni.to_csv(f"{BOLLETTINI_DIR}{os.sep}bollettino-{when_labels[when]}-comuni-latest.csv", index=False)        
    print(f"Bollettino comunale di {when_labels[when]} (versione latest) generato")
    
print("Sto creando il dump delle zone per comuni")

(joined
    .rename(columns={'comune':'comune_nome','den_prov':'provincia_nome','sigla':'provincia_sigla','den_reg':'regione_nome','Zona_all':'zona_codice', 'Nome_zona':'zona_nome'})                                   
    .loc[:, ['pro_com_t','comune_nome','provincia_nome','provincia_sigla','regione_nome','zona_codice','zona_nome']]               
    .to_csv(f"{ZONE_DIR}{os.sep}zone_comuni.csv",index=False)
)

(joined
    .rename(columns={'comune':'comune_nome','den_prov':'provincia_nome','sigla':'provincia_sigla','den_reg':'regione_nome','Zona_all':'zona_codice', 'Nome_zona':'zona_nome'})                                   
    .loc[:, ['pro_com_t','comune_nome','provincia_nome','provincia_sigla','regione_nome','zona_codice','zona_nome','geometry']]    
    .to_file(f"{ZONE_DIR}{os.sep}zone_comuni.geojson", driver='GeoJSON')                            
)

if os.path.exists(TMP_DIR):
    shutil.rmtree(TMP_DIR)  

# Configurazione logging (sovrascrive il file ad ogni esecuzione)
logging.basicConfig(
    filename="/home/user/alert/alert.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode='w'  # sovrascrive ogni volta
)

#Elimino il file giornalieri dato che non faccio il backup

# Percorso dei file da eliminare
file_pattern = "/home/user/alert/data/bollettini/*-bollettino*.csv"

# Trova tutti i file che corrispondono al pattern
files_to_delete = glob.glob(file_pattern)

# Elimina i file
for file_path in files_to_delete:
    try:
        os.remove(file_path)
        print(f"Eliminato: {file_path}")
    except Exception as e:
        print(f"Errore eliminando {file_path}: {e}")

# Percorsi
base_dir = "/home/user/alert"
data_dir = os.path.join(base_dir, "data", "bollettini")
lastrun_path = os.path.join(base_dir, "lastrun.txt")
alert_path = os.path.join(base_dir, "alert.txt")
alert_old_path = os.path.join(base_dir, "alert_old.txt")
send_log_path = os.path.join(base_dir, "send_message.log")
html_path = "/var/www/yoursite/html/alert/index.html"

# Telegram
TOKEN="PUT_HERE_THE_TOKEN"
CHAT_ID = "PUT_HERE_THE_CHATID"


# Timestamp
with open(lastrun_path, "w") as f:
    f.write("Ultimo controllo eseguito il " + datetime.now().strftime("%d/%m/%Y %T") + "\n")

# Ruota alert_old
if os.path.exists(alert_path):
    shutil.copy(alert_path, alert_old_path)
    logging.info("Rotated alert.txt to alert_old.txt")

# Funzione interna per mappare criticità a colore ed emoji
def colore_emoji_allerta(text):
    text = str(text).upper()
    if "NESSUNA" in text:
        return ("NESSUNA ALLERTA", "green", "🟢")
    elif "GIALLA" in text:
        return ("ALLERTA GIALLA", "#CCCC00", "🟡")
    elif "ARANCIONE" in text:
        return ("ALLERTA ARANCIONE", "orange", "🟠")
    elif "ROSSA" in text:
        return ("ALLERTA ROSSA", "red", "🔴")
    else:
        return (text, "black", "")  # fallback

def estrai_zona(df, zona="NOME_ZONA"):
    lines = []
    sel = df[df.iloc[:, 3] == zona]
    for _, r in sel.iterrows():
        # Criticità in colonne specifiche (da controllare struttura CSV)
        # r[4] = criticità generale
        # r[5] = idrogeologico
        # r[6] = temporali
        # r[7] = idraulico
        criticita_list = [r[4], r[5], r[6], r[7]]

        if all("NESSUNA" in str(c).upper() for c in criticita_list):
            # Nessuna allerta
            testo, colore, emoji = colore_emoji_allerta("NESSUNA ALLERTA")
            lines.append(f"{emoji} Zona {zona}\n"
                         f"Bollettino emesso il {r[0][8:10]}/{r[0][5:7]}/{r[0][0:4]} alle ore {r[0][11:19]}\n"
                         f"Inizio validità: {r[1][8:10]}/{r[1][5:7]}/{r[1][0:4]} alle ore {r[1][11:19]}\n"
                         f"Termine validità: {r[2][8:10]}/{r[2][5:7]}/{r[2][0:4]} alle ore {r[2][11:19]}\n"
                         f"{testo}\n\n")
        else:
            lines.append(f"Zona {zona}\n"
                         f"Bollettino emesso il {r[0][8:10]}/{r[0][5:7]}/{r[0][0:4]} alle ore {r[0][11:19]}\n"
                         f"Inizio validità: {r[1][8:10]}/{r[1][5:7]}/{r[1][0:4]} alle ore {r[1][11:19]}\n"
                         f"Termine validità: {r[2][8:10]}/{r[2][5:7]}/{r[2][0:4]} alle ore {r[2][11:19]}\n")

            tipi_allerta = {
                "Criticità": r[4],
                "Idrogeologico": r[5],
                "Temporali": r[6],
                "Idraulico": r[7]
            }
            for tipo, valore in tipi_allerta.items():
                testo, colore, emoji = colore_emoji_allerta(valore)
                lines.append(f"{emoji} {tipo}: {testo}\n")
            lines.append("\n")
    return "".join(lines)

def estrai_comune(df, comune="NOME_COMUNE"):
    lines = []
    sel = df[df.iloc[:, 4] == comune]
    for _, r in sel.iterrows():
        # Colonne criticità come nel CSV dei comuni
        # r[8] = criticità generale
        # r[9] = idrogeologico
        # r[10] = temporali
        # r[11] = idraulico

        criticita_list = [r[8], r[9], r[10], r[11]]

        if all("NESSUNA" in str(c).upper() for c in criticita_list):
            testo, colore, emoji = colore_emoji_allerta("NESSUNA ALLERTA")
            lines.append(f"{emoji} Comune di {comune}\n"
                         f"Bollettino emesso il {r[0][8:10]}/{r[0][5:7]}/{r[0][0:4]} alle ore {r[0][11:19]}\n"
                         f"Inizio validità: {r[1][8:10]}/{r[1][5:7]}/{r[1][0:4]} alle ore {r[1][11:19]}\n"
                         f"Termine validità: {r[2][8:10]}/{r[2][5:7]}/{r[2][0:4]} alle ore {r[2][11:19]}\n"
                         f"{testo}\n\n")
        else:
            lines.append(f"Comune di {comune}\n"
                         f"Bollettino emesso il {r[0][8:10]}/{r[0][5:7]}/{r[0][0:4]} alle ore {r[0][11:19]}\n"
                         f"Inizio validità: {r[1][8:10]}/{r[1][5:7]}/{r[1][0:4]} alle ore {r[1][11:19]}\n"
                         f"Termine validità: {r[2][8:10]}/{r[2][5:7]}/{r[2][0:4]} alle ore {r[2][11:19]}\n")

            tipi_allerta = {
                "Criticità": r[8],
                "Idrogeologico": r[9],
                "Temporali": r[10],
                "Idraulico": r[11]
            }
            for tipo, valore in tipi_allerta.items():
                testo, colore, emoji = colore_emoji_allerta(valore)
                lines.append(f"{emoji} {tipo}: {testo}\n")
            lines.append("\n")
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

# Per la pagina HTML aggiungiamo la colorazione delle righe secondo l'allerta principale (prima criticità non NESSUNA)
def color_line(line):
    line_up = line.upper()
    if "ROSSA" in line_up:
        return f'<span class="alert-red">{line}</span>'
    elif "ARANCIONE" in line_up:
        return f'<span class="alert-orange">{line}</span>'
    elif "GIALLA" in line_up:
        return f'<span class="alert-yellow">{line}</span>'
    elif "NESSUNA ALLERTA" in line_up or "🟢" in line:
        return f'<span class="alert-green">{line}</span>'
    else:
        return line

html_lines = []
for line in (zone_oggi + zone_domani + comune_oggi + comune_domani).splitlines():
    if line.strip() == "":
        html_lines.append("<br>")
    else:
        html_lines.append(color_line(line))

with open(html_path, "w") as fhtml:
    fhtml.write(header)
    fhtml.write("\n".join(html_lines))
    fhtml.write(footer)

logging.info("Pagina HTML aggiornata")

