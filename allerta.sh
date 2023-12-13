#! /bin/bash

#vado nella cartella di lavoro
cd /directory_di_lavoro/

#sposto il vecchio file di alert
if [ -e "/directory_di_lavoro/alert.txt" ]; then
mv /directory_di_lavoro/alert.txt /directory_di_lavoro/alert_old.txt
fi

#salvo un timestamp per pubblicarlo nella pagine web
echo -en "Ultimo controllo eseguito il $(date +"%d/%m/%Y %T") 
"  > lastrun.txt

#parametri per inviare il messaggio telegram
TOKEN="XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
CHAT_ID="YYYYYYYYYYYYYYYYYYY"


#scarico i file dei bollettini
#curl -O -s https://raw.githubusercontent.com/opendatasicilia/DPC-bollettini-criticita-idrogeologica-idraulica/main/data/bollettini/bollettino-oggi-zone-latest.csv
curl -O -s https://raw.githubusercontent.com/opendatasicilia/DPC-bollettini-criticita-idrogeologica-idraulica/main/data/bollettini/bollettino-domani-zone-latest.csv
#curl -O -s https://raw.githubusercontent.com/opendatasicilia/DPC-bollettini-criticita-idrogeologica-idraulica/main/data/bollettini/bollettino-oggi-comuni-latest.csv
curl -O -s https://raw.githubusercontent.com/opendatasicilia/DPC-bollettini-criticita-idrogeologica-idraulica/main/data/bollettini/bollettino-domani-comuni-latest.csv

#processo i dati, ho commentato i dati del bollettino per la giornata odierna che sono meno significativi per il mio scopo

#dati zona ZONA per oggi
# awk -F , '$4 == "ZONA" {print "Zona di validità:", $4, "\n", "Bollettino emesso il", substr($1,9,2)"/"substr($1,6,2)"/"substr($1,1,4) " alle ore " substr($1,12,8), "\n", "Inizio validità:", substr($2,9,2)"/"substr($2,6,2)"/"substr($2,1,4) " alle ore " substr($2,12,8), "\n", "Termine validità",  substr($3,9,2) "/"substr($3,6,2)"/"substr($3,1,4) " alle ore " substr($3,12,8), "\n", "Avviso di criticità:", $5, "\n", "Avviso idrogeologico", $6, "\n", "Avviso temporali", $7, "\n", "Avviso idraulico", $7, "\n" }' bollettino-oggi-zone-latest.csv |awk '{$1=$1};1' > allerta_oggi_zona.txt

#dati zona ZONA per domani
awk -F , '$4 == "ZONA" {print "Zona di validità:", $4, "\n", "Bollettino emesso il", substr($1,9,2)"/"substr($1,6,2)"/"substr($1,1,4) " alle ore " substr($1,12,8), "\n", "Inizio validità:", substr($2,9,2)"/"substr($2,6,2)"/"substr($2,1,4) " alle ore " substr($2,12,8), "\n", "Termine validità",  substr($3,9,2) "/"substr($3,6,2)"/"substr($3,1,4) " alle ore " substr($3,12,8), "\n", "Avviso di criticità:", $5, "\n", "Avviso idrogeologico", $6, "\n", "Avviso temporali", $7, "\n", "Avviso idraulico", $7, "\n" }'  bollettino-domani-zone-latest.csv |awk '{$1=$1};1'  > /directory_di_lavoro/allerta_domani_zona.txt

#dati comune di COMUNE per oggi
# awk -F , '$5 == "COMUNE" {print "Zona di validità, comune di:", $5, "\n", "Bollettino emesso il", substr($1,9,2)"/"substr($1,6,2)"/"substr($1,1,4) " alle ore " substr($1,12,8), "\n", "Inizio validità:", substr($2,9,2)"/"substr($2,6,2)"/"substr($2,1,4) " alle ore " substr($2,12,8), "\n", "Termine validità",  substr($3,9,2) "/"substr($3,6,2)"/"substr($3,1,4) " alle ore " substr($3,12,8), "\n", "Avviso di criticità:", $9, "\n", "Avviso idrogeologico", $10, "\n", "Avviso temporali", $11, "\n", "Avviso idraulico", $12, "\n" }'  bollettino-oggi-comuni-latest.csv |awk '{$1=$1};1' > allerta_oggi_comune.txt

#dati comune di COMUNE per domani
awk -F , '$5 == "COMUNE" {print "Zona di validità: Comune di", $5, "\n", "Bollettino emesso il", substr($1,9,2)"/"substr($1,6,2)"/"substr($1,1,4) " alle ore " substr($1,12,8), "\n", "Inizio validità:", substr($2,9,2)"/"substr($2,6,2)"/"substr($2,1,4) " alle ore " substr($2,12,8), "\n", "Termine validità",  substr($3,9,2) "/"substr($3,6,2)"/"substr($3,1,4) " alle ore " substr($3,12,8), "\n", "Avviso di criticità:", $9, "\n", "Avviso idrogeologico", $10, "\n", "Avviso temporali", $11, "\n", "Avviso idraulico", $12, "\n" }'  bollettino-domani-comuni-latest.csv |awk '{$1=$1};1' > /directory_di_lavoro/allerta_domani_comune.txt


#cerco occorrenze delle parole chiave GIALLA, o ARANCIONE. o ROSSA, anche qui solo per il bollettino relativo a domani
#salvo eventuali occorrenze in un file

# if grep -Eq "GIALLA|ARANCIONE|ROSSA" allerta_oggi_zona.txt; then
	# cat allerta_oggi_zona.txt  >> alert.txt
# else
	# "Nessuna allerta oggi per la zona ZONA"
    # fi

 if grep -Eq "GIALLA|ARANCIONE|ROSSA" /directory_di_lavoro/allerta_domani_zona.txt; then
	cat /directory_di_lavoro/allerta_domani_zona.txt >> /directory_di_lavoro/alert.txt
    fi

 # if grep -Eq "GIALLA|ARANCIONE|ROSSA" allerta_oggi_comune.txt; then
    	# cat allerta_oggi_comune.txt >> alert.txt
# else
	# "Nessuna allerta oggi per il Comune di COMUNE"
    # fi

 if grep -Eq "GIALLA|ARANCIONE|ROSSA" /directory_di_lavoro/allerta_domani_comune.txt; then
    	cat /directory_di_lavoro/allerta_domani_comune.txt >> /directory_di_lavoro/alert.txt
    fi


#il job che esegue lo script gira ogni 30 minuti, se il file esiste ed è diverso dal precedente mando l'aggiornamento via telegram e aggiorno la pagina web

if ! cmp -s "/directory_di_lavoro/alert.txt" "/directory_di_lavoro/alert_old.txt"; then 
	curl -s -X POST https://api.telegram.org/bot$TOKEN/sendMessage -d chat_id=$CHAT_ID --data-urlencode text@alert.txt > /directory_di_lavoro/job_alert.log

fi
# pubblico comunque i file estratti
	lastrun="/directory_di_lavoro/lastrun.txt"
	filename1="/directory_di_lavoro/allerta_domani_zona.txt"
	filename2="/directory_di_lavoro/allerta_domani_comune.txt"
	htmlfile="/var/www/SITOWEB/html/alert/index.html"
	header='<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN"
			 "http://www.w3.org/TR/html4/strict.dtd">
			 <meta charset="UTF-8">
			 <meta http-equiv="Content-type" content="text/html; charset=UTF-8">

	<head>
		<title>Allerta meteo</title>
		<style type="text/css">
		pre{font-size:200%;}
		</style>
	</head>
	<body>
		<pre>
	'
	footer='
		</pre>
	</html>'

	{
	 printf "%s\n" "$header"
	 cat "$lastrun"
	 printf "\n" 
	 cat "$filename1"
	 cat "$filename2"
	 printf "%s\n" "$footer"
	} > "$htmlfile"
