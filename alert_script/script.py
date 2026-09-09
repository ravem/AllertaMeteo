#!/usr/bin/env python3
"""
Script principale per il monitoraggio allerte meteo Protezione Civile.

Flusso:
  1. Scarica il zip dei bollettini dal repository DPC
  2. Estrae gli shapefile e genera CSV per zone e comuni (oggi e domani)
  3. Aggiorna la mappa zone-comuni
  4. Carica i CSV e verifica la presenza di allerte per gli utenti iscritti
  5. Invia notifiche Telegram per allerte nuove o modificate
  6. Genera alert.txt e pagina HTML
"""

import hashlib
import json
import logging
import os
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

import config
from subscriptions import get_subscriptions_by_zone

# ── Logging ─────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=config.ALERT_LOG,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode="a",
)

log = logging.getLogger(__name__)

# ── Costanti ────────────────────────────────────────────────────────────
KEYWORDS_ALLERTA = ["GIALLA", "ARANCIONE", "ROSSA"]
HTML_PATH = config.HTML_PATH
WEB_ZONE_DIR = HTML_PATH.parent / "data" / "zone"

COLONNE_ZONE = [
    "data_pubblicazione", "data_validita_inizio", "data_validita_fine",
    "zona_codice", "zona_nome", "avviso_criticita", "avviso_idrogeologico",
    "avviso_temporali", "avviso_idraulico",
]
COLONNE_COMUNI = [
    "data_pubblicazione", "data_validita_inizio", "data_validita_fine",
    "pro_com_t", "comune_nome", "provincia_nome", "regione_nome",
    "zona_codice", "zona_nome", "avviso_criticita", "avviso_idrogeologico",
    "avviso_temporali", "avviso_idraulico",
]


# ═══════════════════════════════════════════════════════════════════════
# FASE 1 – Download e generazione CSV
# ═══════════════════════════════════════════════════════════════════════

def fase1_scarica_e_processa():
    """Scarica il zip DPC, estrae shapefile e genera CSV bollettini."""
    tmp_dir = config.TMP_DIR
    data_dir = config.BOLLETTINI_DIR

    # Crea tmp
    tmp_dir.mkdir(parents=True, exist_ok=True)
    print("Downloading bollettini Protezione Civile")

    # Scarica zip
    zip_path = tmp_dir / "latest_all.zip"
    try:
        r = requests.get(config.PROTEZIONE_CIVILE_BOLLETTINI_URL,
                         timeout=config.REQUESTS_TIMEOUT)
        r.raise_for_status()
        with open(zip_path, "wb") as f:
            f.write(r.content)
    except Exception as e:
        log.error(f"Errore download zip DPC: {e}")
        print(f"ERRORE download: {e}")
        return

    print("Unzipping dati scaricati...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(tmp_dir)

    # Trova i file shapefile (today / tomorrow)
    shp_today = sorted(tmp_dir.glob("*_today.shp"))
    shp_tomorrow = sorted(tmp_dir.glob("*_tomorrow.shp"))

    if not shp_today or not shp_tomorrow:
        log.error("Shapefile today o tomorrow non trovati nello zip")
        print("ERRORE: shapefile mancanti")
        return

    # Leggi gli shapefile e genera CSV
    data_dir.mkdir(parents=True, exist_ok=True)

    # Estrai timestamp dal nome del file (es. 20260908_1519)
    timestamp_match = re.search(r"(\d{8}_\d{4})_", shp_today[0].stem)
    data_pub_str = ""
    if timestamp_match:
        ts = timestamp_match.group(1)
        data_pub_str = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}T{ts[9:11]}:{ts[11:13]}:00"

    for prefix, shp_files in [("oggi", shp_today), ("domani", shp_tomorrow)]:
        shp_path = shp_files[0]
        print(f"Lettura shapefile: {shp_path.name}")

        # Import geopandas (installato sul server)
        try:
            import geopandas as gpd
            gdf = gpd.read_file(shp_path)
        except ImportError:
            try:
                from dbfread import DBF
                dbf_path = shp_path.with_suffix(".dbf")
                records = list(DBF(dbf_path))
                gdf = pd.DataFrame(records)
            except ImportError:
                log.error("Né geopandas né dbfread disponibili")
                print("ERRORE: librerie mancanti (geopandas o dbfread)")
                return

        # Salva geometria per join spaziale con comuni
        geometria = gdf["geometry"] if "geometry" in gdf.columns else None

        # Droppa geometria per manipolazione tabellare
        if "geometry" in gdf.columns:
            gdf = gdf.drop(columns=["geometry"])

        # Rinomina colonne secondo schema atteso
        rename_map = _build_column_map(gdf.columns)
        if rename_map:
            gdf = gdf.rename(columns=rename_map)

        # Aggiungi colonne data
        if data_pub_str:
            gdf["data_pubblicazione"] = data_pub_str
            if prefix == "oggi":
                giorno = data_pub_str[:10]
                gdf["data_validita_inizio"] = f"{giorno}T00:00:00"
                gdf["data_validita_fine"] = f"{giorno}T23:59:59"
            else:
                from datetime import timedelta
                pub_dt = datetime.fromisoformat(data_pub_str)
                domani = (pub_dt + timedelta(days=1)).strftime("%Y-%m-%d")
                gdf["data_validita_inizio"] = f"{domani}T00:00:00"
                gdf["data_validita_fine"] = f"{domani}T23:59:59"

        # Assicura colonne standard
        for col in COLONNE_ZONE:
            if col not in gdf.columns:
                gdf[col] = ""

        # Salva CSV zone
        zone_cols = [c for c in COLONNE_ZONE if c in gdf.columns]
        df_zone = gdf[zone_cols].copy()
        zone_csv = data_dir / f"bollettino-{prefix}-zone-latest.csv"
        df_zone.to_csv(zone_csv, index=False)
        print(f"Bollettino zone {prefix} generato")
        log.info(f"Created {len(df_zone)} records (zone {prefix})")

        # Genera CSV comuni via join spaziale con dataset comuni italiani
        df_comuni = _genera_csv_comuni(geometria, gdf, prefix, tmp_dir, data_pub_str)
        comuni_csv = data_dir / f"bollettino-{prefix}-comuni-latest.csv"
        df_comuni.to_csv(comuni_csv, index=False)
        print(f"Bollettino comuni {prefix} generato")
        log.info(f"Created {len(df_comuni)} records (comuni {prefix})")

    # Genera/Carica dump zone per comuni
    print("Creazione dump zone per comuni...")
    _genera_dump_zone(tmp_dir, data_dir)

    # Pulisci file bollettini giornalieri (con data nel nome)
    puliti = 0
    for f in data_dir.glob("????????-bollettino-*-*.csv"):
        f.unlink(missing_ok=True)
        puliti += 1
        print(f"  Eliminato: {f.name}")
    log.info(f"Puliti {puliti} file bollettini giornalieri")

    # Pulisci tmp
    shutil.rmtree(tmp_dir, ignore_errors=True)

    print("Elaborazione completata.")


def _build_column_map(colonne):
    """Mappa nomi colonne DBF ai nomi standard.
    I nomi reali dal DPC sono: Zona_all, Nome_zona, Criticita,
    Idrogeo, Temporali, Idraulico.
    """
    mapping = {}
    NOMI_DBF = {
        "zona_all": "zona_codice",
        "nome_zona": "zona_nome",
        "criticita": "avviso_criticita",
        "idrogeo": "avviso_idrogeologico",
        "temporali": "avviso_temporali",
        "idraulico": "avviso_idraulico",
    }
    for col in colonne:
        cl = col.lower().strip()
        if cl in NOMI_DBF:
            # Non rinominare se ha già il nome target
            if col != NOMI_DBF[cl]:
                mapping[col] = NOMI_DBF[cl]
        else:
            # Fallback generico per altri nomi
            if "pubblicaz" in cl or "pubb" in cl:
                mapping[col] = "data_pubblicazione"
            elif "valid" in cl and ("iniz" in cl or "in" == cl or cl.endswith("_i")):
                mapping[col] = "data_validita_inizio"
            elif "valid" in cl and ("fine" in cl or "fin" in cl or cl.endswith("_f")):
                mapping[col] = "data_validita_fine"
    return mapping


def _genera_csv_comuni(geometria_zone, df_zone, prefix, tmp_dir, data_pub_str):
    """
    Genera CSV per comuni tramite join spaziale tra i punti dei comuni
    italiani e i poligoni delle zone di allerta.
    Se il join non è possibile, restituisce un DataFrame vuoto.
    """
    try:
        import geopandas as gpd
    except ImportError:
        return pd.DataFrame(columns=COLONNE_COMUNI)

    if geometria_zone is None:
        return pd.DataFrame(columns=COLONNE_COMUNI)

    # Crea GeoDataFrame delle zone con geometria
    gdf_zone = gpd.GeoDataFrame(df_zone, geometry=geometria_zone, crs="EPSG:4326")

    # Carica/scarica comuni italiani
    comuni_csv_path = tmp_dir / "comuni_italiani.csv"
    try:
        if not comuni_csv_path.exists():
            r = requests.get(config.COMUNI_ITALIANI_URL, timeout=config.REQUESTS_TIMEOUT)
            r.raise_for_status()
            with open(comuni_csv_path, "wb") as f:
                f.write(r.content)
        df_comuni = pd.read_csv(comuni_csv_path)
    except Exception as e:
        log.warning(f"Errore caricamento comuni: {e}")
        return pd.DataFrame(columns=COLONNE_COMUNI)

    # Verifica presenza coordinate
    lat_col = next((c for c in ["lat", "Lat", "latitude", "y"] if c in df_comuni.columns), None)
    lon_col = next((c for c in ["lng", "Lng", "lon", "Lon", "longitude", "x"] if c in df_comuni.columns), None)
    if not lat_col or not lon_col:
        return pd.DataFrame(columns=COLONNE_COMUNI)

    # Crea GeoDataFrame punti dai comuni
    gdf_comuni = gpd.GeoDataFrame(
        df_comuni,
        geometry=gpd.points_from_xy(df_comuni[lon_col], df_comuni[lat_col]),
        crs="EPSG:4326",
    )

    # Join spaziale: punti comuni dentro poligoni zone
    gdf_joined = gpd.sjoin(gdf_comuni, gdf_zone, how="inner", predicate="within")

    if gdf_joined.empty:
        return pd.DataFrame(columns=COLONNE_COMUNI)

    # Mappa nomi colonne comuni
    rename_com = {}
    for c in gdf_joined.columns:
        cl = c.lower().strip()
        if cl in ("pro_com_t", "comune_nome", "provincia_nome", "regione_nome"):
            rename_com[c] = cl
        elif "comune" in cl and "nome" not in cl:
            rename_com[c] = "comune_nome"
        elif "provincia" in cl:
            rename_com[c] = "provincia_nome"
        elif "regione" in cl:
            rename_com[c] = "regione_nome"
        elif "istat" in cl or "pro_com" in cl:
            rename_com[c] = "pro_com_t"

    gdf_joined = gdf_joined.rename(columns=rename_com)

    # Costruisci output
    result = pd.DataFrame()
    result["data_pubblicazione"] = data_pub_str
    if "data_validita_inizio" in df_zone.columns:
        result["data_validita_inizio"] = gdf_joined["data_validita_inizio"]
        result["data_validita_fine"] = gdf_joined["data_validita_fine"]
    result["pro_com_t"] = gdf_joined.get("pro_com_t", "")
    result["comune_nome"] = gdf_joined.get("comune_nome", "")
    result["provincia_nome"] = gdf_joined.get("provincia_nome", "")
    result["regione_nome"] = gdf_joined.get("regione_nome", "")
    result["zona_codice"] = gdf_joined.get("zona_codice", "")
    result["zona_nome"] = gdf_joined.get("zona_nome", "")
    for col in ["avviso_criticita", "avviso_idrogeologico",
                "avviso_temporali", "avviso_idraulico"]:
        if col in gdf_joined.columns:
            result[col] = gdf_joined[col]

    return result.drop_duplicates(subset=["comune_nome", "zona_codice", "data_validita_inizio"])


def _genera_dump_zone(tmp_dir, data_dir):
    """
    Genera/Carica zone.csv e zone_comuni.csv.
    Legge i CSV appena generati per estrarre la mappa zona-codice/zona-nome
    e la mappa comune-zona.
    """
    # zone.csv: lista zone con codice e nome
    zone_files = list(data_dir.glob("bollettino-*-zone-latest.csv"))
    if not zone_files:
        return

    df_zone = pd.read_csv(zone_files[0])
    if "zona_codice" in df_zone.columns:
        if "zona_nome" not in df_zone.columns:
            df_zone["zona_nome"] = df_zone["zona_codice"]
        zone_map = df_zone[["zona_codice", "zona_nome"]].drop_duplicates()
        zone_map.to_csv(data_dir.parent / "zone" / "zone.csv", index=False)

    # zone_comuni.csv: mappa comune -> zona
    comuni_files = list(data_dir.glob("bollettino-*-comuni-latest.csv"))
    if comuni_files:
        df_com = pd.read_csv(comuni_files[0])
        cols = [c for c in ["pro_com_t", "comune_nome", "provincia_nome",
                             "regione_nome", "zona_codice", "zona_nome"]
                if c in df_com.columns]
        if not cols:
            return
        df_com[cols].drop_duplicates().to_csv(
            data_dir.parent / "zone" / "zone_comuni.csv", index=False)


# ═══════════════════════════════════════════════════════════════════════
# FASE 2 – Notifiche e HTML
# ═══════════════════════════════════════════════════════════════════════

def fase2_notifiche_html():
    """Carica i CSV, confronta con notifiche già inviate e invia nuovi alert."""
    # Carica registro notifiche
    registro = _carica_registro()

    # Carica dati correnti
    df_zone_oggi, df_zone_domani, df_comuni_oggi, df_comuni_domani = \
        _carica_bollettini()

    if df_zone_oggi is None:
        log.warning("Nessun dato da elaborare")
        return

    # Calcola fingerprint complessivo dei dati
    fingerprint = _calcola_fingerprint(
        df_zone_oggi, df_zone_domani, df_comuni_oggi, df_comuni_domani
    )

    # Trova tutte le zone con allerta (sia da zone che da comuni)
    zone_allerta = _trova_zone_allertate(df_zone_oggi, df_zone_domani)

    if not zone_allerta:
        log.info("Nessuna allerta attiva in nessuna zona")
    else:
        log.info(f"Zone con allerta trovate: {len(zone_allerta)}")

    # Per ogni zona in allerta, trova iscritti e invia notifiche
    notifiche_inviate = 0
    for zona_codice, alerta_info in zone_allerta.items():
        iscritti = get_subscriptions_by_zone(zona_codice)
        if not iscritti:
            continue

        for iscritto in iscritti:
            if _invia_se_nuovo(registro, iscritto, alerta_info, fingerprint):
                notifiche_inviate += 1

    # Pulisci notifiche vecchie (7+ giorni)
    vecchie = _pulisci_notifiche_vecchie(registro)
    if vecchie:
        log.info(f"Pulite {vecchie} notifiche vecchie dal registro")

    # Salva registro
    _salva_registro(registro)
    log.info(f"Registro notifiche salvato: {len(registro)} chiavi")

    # Se non ci sono notifiche da inviare ma il fingerprint è cambiato,
    # generiamo comunque alert.txt e HTML (aggiornamento dati)
    _genera_alert_txt(df_zone_oggi, df_zone_domani, df_comuni_oggi, df_comuni_domani)
    _genera_html(df_zone_oggi, df_zone_domani, df_comuni_oggi, df_comuni_domani)
    _copia_file_zone()


def _carica_registro() -> dict:
    """Carica il registro delle notifiche già inviate."""
    path = config.SENT_NOTIFICATIONS_JSON
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                log.info(f"Registro notifiche caricato: {len(data)} chiavi presenti")
                return data
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _salva_registro(registro: dict):
    """Salva il registro notifiche."""
    path = config.SENT_NOTIFICATIONS_JSON
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(registro, f, indent=2, ensure_ascii=False)
    os.replace(str(tmp), str(path))


def _carica_bollettini():
    """Carica i CSV dei bollettini."""
    bd = config.BOLLETTINI_DIR
    try:
        zo = pd.read_csv(bd / "bollettino-oggi-zone-latest.csv")
        zd = pd.read_csv(bd / "bollettino-domani-zone-latest.csv")
        co = pd.read_csv(bd / "bollettino-oggi-comuni-latest.csv")
        cd = pd.read_csv(bd / "bollettino-domani-comuni-latest.csv")
        return zo, zd, co, cd
    except (FileNotFoundError, pd.errors.EmptyDataError) as e:
        log.warning(f"CSV non trovati: {e}")
        return None, None, None, None


def _calcola_fingerprint(*dfs) -> str:
    """Calcola hash SHA256 del contenuto dei dataframe."""
    h = hashlib.sha256()
    for df in dfs:
        if df is not None:
            h.update(pd.util.hash_pandas_object(df).values.tobytes())
    return h.hexdigest()[:40]


def _trova_zone_allertate(df_oggi, df_domani) -> dict:
    """
    Analizza i dataframe e restituisce un dict:
      { zona_codice: { "oggi": {...} or None, "domani": {...} or None } }
    Solo zone con almeno un'allerta (GIALLA/ARANCIONE/ROSSA).
    """
    zone = {}

    def _ha_allerta(*valori):
        for v in valori:
            v_upper = str(v).upper()
            for k in KEYWORDS_ALLERTA:
                if k in v_upper:
                    return True
        return False

    for giorno, df in [("oggi", df_oggi), ("domani", df_domani)]:
        if df is None:
            continue
        for _, row in df.iterrows():
            zona = str(row.get("zona_codice", "")).strip()
            if not zona:
                continue

            crit = row.get("avviso_criticita", "")
            idro = row.get("avviso_idrogeologico", "")
            temp = row.get("avviso_temporali", "")
            idra = row.get("avviso_idraulico", "")

            if not _ha_allerta(crit, idro, temp, idra):
                continue

            if zona not in zone:
                zone[zona] = {"oggi": None, "domani": None}
            zone[zona][giorno] = {
                "zona_codice": zona,
                "zona_nome": str(row.get("zona_nome", "")).strip(),
                "data_pubblicazione": row.get("data_pubblicazione", ""),
                "data_validita_inizio": row.get("data_validita_inizio", ""),
                "data_validita_fine": row.get("data_validita_fine", ""),
                "avviso_criticita": crit,
                "avviso_idrogeologico": idro,
                "avviso_temporali": temp,
                "avviso_idraulico": idra,
            }

    return zone


def _formatta_livello_allerta(testo_originale: str) -> str:
    """
    Estrae il livello di allerta dal testo e lo restituisce
    con emoji colorata e testo semplificato.

    Esempi:
      "Ordinaria / ALLERTA GIALLA"  -> "🟡 Allerta Gialla"
      ""                             -> "⚪ Nessuna allerta"
      "Assenza di fenomeni..."       -> "⚪ Nessuna allerta"
    """
    if not testo_originale or not testo_originale.strip():
        return "⚪ Nessuna allerta"

    # Prendi la parte dopo l'ultimo "/" se presente
    livello = testo_originale
    if "/" in testo_originale:
        livello = testo_originale.rsplit("/", 1)[-1].strip()

    livello_up = livello.upper()

    if "ROSSA" in livello_up:
        return "🔴 Allerta Rossa"
    elif "ARANCIONE" in livello_up:
        return "🟠 Allerta Arancione"
    elif "GIALLA" in livello_up:
        return "🟡 Allerta Gialla"
    elif "NESSUNA" in livello_up or "ASSENZA" in livello_up or "SENZA" in livello_up:
        return "🟢 Nessuna allerta"
    else:
        return f"🟢 {livello}"


def _formatta_data_ora(data_iso: str) -> str:
    """Converte data ISO (2026-09-08T15:19:00) in dd/mm/yyyy hh:mm."""
    if not data_iso:
        return ""
    try:
        # Rimuovi eventuale fuso orario (es. +00:00, Z)
        data_pulita = data_iso.replace("Z", "").split("+")[0].split("-")[0] if data_iso.count("-") > 2 else data_iso
        # Prova formato ISO completo
        for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d"]:
            try:
                dt = datetime.strptime(data_iso[:19], fmt)
                return dt.strftime("%d/%m/%Y %H:%M")
            except ValueError:
                continue
        # Fallback: restituisci la data originale troncata
        return data_iso[:10]
    except Exception:
        return data_iso[:10]


def _invia_se_nuovo(registro: dict, iscritto: dict,
                     alerta_info: dict, fingerprint: str) -> bool:
    """
    Invia notifica se l'allerta per questa iscrizione è nuova o modificata.
    Confronto basato su sub_id + zona_codice + data_validita_inizio + criticità.
    """
    sub_id = iscritto.get("id", "?")
    chat_id = iscritto.get("chat_id")
    if not chat_id:
        return False

    # Costruisci il messaggio per oggi e domani
    parti_giorno = []
    for giorno in ["oggi", "domani"]:
        info = alerta_info.get(giorno)
        if info is None:
            continue
        # Verifica se c'è effettivamente un'allerta
        crit_vals = [
            str(info.get("avviso_criticita", "")),
            str(info.get("avviso_idrogeologico", "")),
            str(info.get("avviso_temporali", "")),
            str(info.get("avviso_idraulico", "")),
        ]
        if not any(k in c.upper() for c in crit_vals for k in KEYWORDS_ALLERTA):
            continue
        parti_giorno.append((giorno, info))

    if not parti_giorno:
        return False

    # Costruisci il testo del messaggio
    comune = iscritto.get("comune", "?")
    provincia = iscritto.get("provincia", "")
    zona_codice = (iscritto.get("zona_codice") or "").strip()
    zona_nome = (iscritto.get("zona_nome") or "").strip()

    # Se manca zona_codice o zona_nome, prova a prenderli dai dati allerta
    if not zona_codice or not zona_nome:
        info_oggi = alerta_info.get("oggi") or {}
        info_domani = alerta_info.get("domani") or {}
        if not zona_codice:
            zona_codice = (info_oggi.get("zona_codice") or info_domani.get("zona_codice") or "")
        if not zona_nome:
            zona_nome = (info_oggi.get("zona_nome") or info_domani.get("zona_nome") or "")

    parte_zona = f" — Zona {zona_codice}" if zona_codice else ""
    parte_zona_nome = f" ({zona_nome})" if zona_nome else ""

    lines = ["ALLERTA METEO PER LA TUA ZONA!"]

    for giorno, info in parti_giorno:
        giorno_label = "OGGI" if giorno == "oggi" else "DOMANI"
        lines.append("")
        lines.append(f"GIORNO: {giorno_label}")
        lines.append(f"COMUNE: {comune} ({provincia}){parte_zona}{parte_zona_nome}")
        lines.append("")
        lines.append(f"Idrogeologico: {_formatta_livello_allerta(info.get('avviso_idrogeologico', ''))}")
        lines.append(f"Temporali: {_formatta_livello_allerta(info.get('avviso_temporali', ''))}")
        lines.append(f"Idraulico: {_formatta_livello_allerta(info.get('avviso_idraulico', ''))}")
        lines.append("")
        data_pub = str(info.get("data_pubblicazione", ""))
        data_inizio = str(info.get("data_validita_inizio", ""))
        data_fine = str(info.get("data_validita_fine", ""))
        if data_pub:
            lines.append(f"BOLLETTINO PUBBLICATO: {_formatta_data_ora(data_pub)}")
        if data_inizio and data_fine:
            lines.append(f"VALIDITA: {_formatta_data_ora(data_inizio)} ➜ {_formatta_data_ora(data_fine)}")

    testo = "\n".join(lines)

    # Calcola chiave univoca per confronto
    # Combina sub_id, zona_codice, e fingerprint delle date+criticità
    chiave_base = f"{sub_id}_{zona_codice}"
    dettagli = ""
    for giorno, info in parti_giorno:
        dettagli += f"|{info.get('data_validita_inizio','')}|{info.get('data_validita_fine','')}"
        dettagli += f"|{info.get('avviso_criticita','')}|{info.get('avviso_idrogeologico','')}"
        dettagli += f"|{info.get('avviso_temporali','')}|{info.get('avviso_idraulico','')}"
    msg_hash = hashlib.sha256(dettagli.encode()).hexdigest()[:20]
    chiave = f"{chiave_base}_{msg_hash}"

    # Verifica se già inviato
    if chiave in registro:
        return False

    # Invia Telegram
    if _invia_telegram(chat_id, testo):
        registro[chiave] = {
            "sent_at": datetime.now().isoformat(),
            "sub_id": sub_id,
            "comune": comune,
            "zona_codice": zona_codice,
        }
        log.info(f"Notifica inviata a {chat_id} ({comune}, zona {zona_codice})")
        return True
    else:
        log.warning(f"Broadcast status fallito per {chat_id} ({comune})")
        return False


def _invia_telegram(chat_id: int, testo: str) -> bool:
    """Invia un messaggio Telegram. Restituisce True se successo."""
    if not config.TOKEN:
        log.error("TELEGRAM_TOKEN non impostato")
        return False

    # Limita a 4096 caratteri (limite Telegram)
    if len(testo) > 4000:
        testo = testo[:4000] + "\n\n[TRONCATO]"

    try:
        resp = requests.post(
            config.telegram_api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": testo,
                "parse_mode": "HTML",
            },
            timeout=config.REQUESTS_TIMEOUT,
        )
        if resp.status_code == 200:
            return True
        else:
            log.warning(f"Broadcast status {resp.status_code} per {chat_id}: {resp.text[:200]}")
            return False
    except requests.RequestException as e:
        log.error(f"Errore invio Telegram a {chat_id}: {e}")
        return False


def _pulisci_notifiche_vecchie(registro: dict) -> int:
    """Rimuove notifiche più vecchie di 7 giorni."""
    now = datetime.now()
    da_rimuovere = []
    for chiave, info in registro.items():
        if isinstance(info, dict) and "sent_at" in info:
            try:
                sent = datetime.fromisoformat(info["sent_at"])
                if (now - sent).days >= 7:
                    da_rimuovere.append(chiave)
            except (ValueError, TypeError):
                da_rimuovere.append(chiave)
    for k in da_rimuovere:
        del registro[k]
    return len(da_rimuovere)


# ═══════════════════════════════════════════════════════════════════════
# Utility: alert.txt e HTML
# ═══════════════════════════════════════════════════════════════════════

def _formatta_allerta_come_testo(df_zone_oggi, df_zone_domani,
                                  df_comuni_oggi, df_comuni_domani) -> str:
    """Genera un riepilogo testuale delle allerte per alert.txt."""
    lines = []
    for giorno, df_z, df_c in [
        ("OGGI", df_zone_oggi, df_comuni_oggi),
        ("DOMANI", df_zone_domani, df_comuni_domani),
    ]:
        if df_z is None:
            continue
        lines.append(f"=== {giorno} ===")
        for _, r in df_z.iterrows():
            crit = str(r.get("avviso_criticita", ""))
            if any(k in crit.upper() for k in KEYWORDS_ALLERTA):
                zona = r.get("zona_codice", "")
                pub = r.get("data_pubblicazione", "")
                val_i = r.get("data_validita_inizio", "")
                val_f = r.get("data_validita_fine", "")
                lines.append(f"[{zona}] Criticita: {crit}")
                lines.append(f"     Pubblicato: {pub}")
                lines.append(f"     Validita: {val_i} -> {val_f}")
                lines.append(f"     Idrogeologico: {r.get('avviso_idrogeologico','')}")
                lines.append(f"     Temporali: {r.get('avviso_temporali','')}")
                lines.append(f"     Idraulico: {r.get('avviso_idraulico','')}")
                lines.append("")
    return "\n".join(lines)


def _genera_alert_txt(*dfs):
    """Genera alert.txt con riepilogo allerte."""
    testo = _formatta_allerta_come_testo(*dfs)
    config.ALERT_TXT.write_text(testo, encoding="utf-8")
    log.info("Generato alert.txt")


def _genera_html(*dfs):
    """Genera la pagina HTML."""
    df_zo, df_zd, df_co, df_cd = dfs

    style = """
    <style>
        body{font-family:'Roboto',sans-serif; font-size:1em; white-space:pre-wrap; background:#f5f5f5; padding:20px;}
        h1{color:#333;}
        .alert-green{color:green;}
        .alert-yellow{color:#CCCC00;}
        .alert-orange{color:orange;}
        .alert-red{color:red;}
        .giorno{margin-top:20px;font-weight:bold;font-size:1.2em;color:#555;}
    </style>
    """

    header = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
    <title>Allerta Meteo</title>
    <link href="https://fonts.googleapis.com/css2?family=Roboto&display=swap" rel="stylesheet">
    {style}</head><body>
    <h1>Allerte Meteo</h1>
    <p><em>Ultimo aggiornamento: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</em></p>
    """

    body_lines = []
    for giorno, df_z in [("OGGI", df_zo), ("DOMANI", df_zd)]:
        if df_z is None:
            continue
        body_lines.append(f'<div class="giorno">=== {giorno} ===</div>')
        for _, r in df_z.iterrows():
            crit = str(r.get("avviso_criticita", ""))
            css = "alert-green"
            if "ROSSA" in crit.upper():
                css = "alert-red"
            elif "ARANCIONE" in crit.upper():
                css = "alert-orange"
            elif "GIALLA" in crit.upper():
                css = "alert-yellow"

            zona = r.get("zona_codice", "")
            pub = r.get("data_pubblicazione", "")
            val_i = r.get("data_validita_inizio", "")
            val_f = r.get("data_validita_fine", "")
            idro = r.get("avviso_idrogeologico", "")
            temp = r.get("avviso_temporali", "")
            idra = r.get("avviso_idraulico", "")

            body_lines.append(
                f'<div class="{css}">')
            body_lines.append(f'  <b>Zona {zona}</b><br>')
            body_lines.append(f'  Criticita: {crit}<br>')
            body_lines.append(f'  Idrogeologico: {idro}<br>')
            body_lines.append(f'  Temporali: {temp}<br>')
            body_lines.append(f'  Idraulico: {idra}<br>')
            body_lines.append(f'  <small>Pubblicato: {pub} | '
                              f'Validita: {val_i} -> {val_f}</small>')
            body_lines.append('</div><br>')

    footer = "</body></html>"
    html_content = header + "\n".join(body_lines) + footer

    HTML_PATH.parent.mkdir(parents=True, exist_ok=True)
    HTML_PATH.write_text(html_content, encoding="utf-8")
    log.info(f"Pagina HTML aggiornata: {HTML_PATH}")


def _copia_file_zone():
    """Copia zone.csv e zone_comuni.csv nella directory web."""
    src_zone = config.ZONE_DIR / "zone.csv"
    src_comuni = config.ZONE_DIR / "zone_comuni.csv"

    WEB_ZONE_DIR.mkdir(parents=True, exist_ok=True)

    if src_zone.exists():
        shutil.copy2(src_zone, WEB_ZONE_DIR / "zone.csv")
        log.info(f"Copiato zone.csv -> {WEB_ZONE_DIR / 'zone.csv'}")
    if src_comuni.exists():
        shutil.copy2(src_comuni, WEB_ZONE_DIR / "zone_comuni.csv")
        log.info(f"Copiato zone_comuni.csv -> {WEB_ZONE_DIR / 'zone_comuni.csv'}")


# ═══════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════

def main():
    config.ensure_dirs()

    # Fase 1: download e generazione CSV
    fase1_scarica_e_processa()

    # Fase 2: carica dati, invia notifiche, genera HTML
    fase2_notifiche_html()

    # Timestamp ultima esecuzione
    config.LASTRUN_TXT.write_text(
        f"Ultimo controllo eseguito il "
        f"{datetime.now().strftime('%d/%m/%Y %T')}\n",
        encoding="utf-8",
    )

    log.info("Script completato con successo")


if __name__ == "__main__":
    main()
