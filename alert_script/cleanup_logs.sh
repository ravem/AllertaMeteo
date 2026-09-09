#!/bin/bash
# Pulizia settimanale dei file di log del sistema AllertaMeteo.
# NON tocca file di stato necessari al funzionamento (sent_notifications.json,
# subscriptions.json, state.json, alert.txt, lastrun.txt, bot_offset.txt, ecc.).
# Da eseguire con crontab ogni domenica a mezzanotte.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CFD_DIR="$SCRIPT_DIR/cfd"
KEEP_LINES=500

echo "[$(date '+%Y-%m-%d %H:%M:%S')] --- Pulizia settimanale log AllertaMeteo ---"

# Tronca i file di log alle ultime KEEP_LINES righe
for logfile in \
    "$SCRIPT_DIR/alert.log" \
    "$SCRIPT_DIR/send_message.log" \
    "$SCRIPT_DIR/api_server.log" \
    "$SCRIPT_DIR/api_server_error.log" \
    "$SCRIPT_DIR/bot_listener.log" \
    "$SCRIPT_DIR/bot_listener_error.log" \
    "$CFD_DIR/cfd.log"; do
    if [ -f "$logfile" ]; then
        lines=$(wc -l < "$logfile" 2>/dev/null || echo 0)
        if [ "$lines" -gt "$KEEP_LINES" ]; then
            tail -n "$KEEP_LINES" "$logfile" > "${logfile}.tmp" && mv "${logfile}.tmp" "$logfile"
            echo "  Troncato $logfile ($lines righe -> $KEEP_LINES)"
        else
            echo "  $logfile: $lines righe, OK"
        fi
    else
        echo "  $logfile: non presente"
    fi
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Pulizia completata."
