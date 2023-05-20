#! /bin/bash

#pulisco 
clear
rm alert.txt

#parametri per inviare il messaggio telegram
TOKEN="XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
CHAT_ID="XXXXXXXXXXXXXXX"


#scarico i file dei bollettini
curl -O -s https://raw.githubusercontent.com/opendatasicilia/DPC-bollettini-criticita-idrogeologica-idraulica/main/data/bollettini/bollettino-oggi-zone-latest.csv
curl -O -s https://raw.githubusercontent.com/opendatasicilia/DPC-bollettini-criticita-idrogeologica-idraulica/main/data/bollettini/bollettino-domani-zone-latest.csv
curl -O -s https://raw.githubusercontent.com/opendatasicilia/DPC-bollettini-criticita-idrogeologica-idraulica/main/data/bollettini/bollettino-oggi-comuni-latest.csv
curl -O -s https://raw.githubusercontent.com/opendatasicilia/DPC-bollettini-criticita-idrogeologica-idraulica/main/data/bollettini/bollettino-domani-comuni-latest.csv

#processo i dati, e ho commentato i dati del bolletino per la giornata odierna che sono meno significativi per il mio scopo
# i valori XXXYYYY e xxxyyy vanno rispettivamente sostituiti con il nome della zona di riferimento, e del comune di interesse

#dati zona XXXYYYY per oggi
# awk -F , '$4 == "XXXYYYY" {print "Zona di validità:", $4, "\n", "Bollettino emesso il", substr($1,9,2)"/"substr($1,6,2)"/"substr($1,1,4) " alle ore " substr($1,12,8), "\n", "Inizio validità:", substr($2,9,2)"/"substr($2,6,2)"/"substr($2,1,4) " alle ore " substr($2,12,8), "\n", "Termine validità",  substr($3,9,2) "/"substr($3,6,2)"/"substr($3,1,4) " alle ore " substr($3,12,8), "\n", "Avviso di criticità:", $5, "\n", "Avviso idrogeologico", $6, "\n", "Avviso temporali", $7, "\n", "Avviso idraulico", $7, "\n" }' bollettino-oggi-zone-latest.csv |awk '{$1=$1};1' > allerta_oggi_zona.txt

#dati zona XXXYYYY per domani
awk -F , '$4 == "XXXYYYY" {print "Zona di validità:", $4, "\n", "Bollettino emesso il", substr($1,9,2)"/"substr($1,6,2)"/"substr($1,1,4) " alle ore " substr($1,12,8), "\n", "Inizio validità:", substr($2,9,2)"/"substr($2,6,2)"/"substr($2,1,4) " alle ore " substr($2,12,8), "\n", "Termine validità",  substr($3,9,2) "/"substr($3,6,2)"/"substr($3,1,4) " alle ore " substr($3,12,8), "\n", "Avviso di criticità:", $5, "\n", "Avviso idrogeologico", $6, "\n", "Avviso temporali", $7, "\n", "Avviso idraulico", $7, "\n" }'  bollettino-domani-zone-latest.csv |awk '{$1=$1};1'  > allerta_domani_zona.txt

#dati comune di xxxyyy per oggi
# awk -F , '$5 == "xxxyyy" {print "Zona di validità, comune di:", $5, "\n", "Bollettino emesso il", substr($1,9,2)"/"substr($1,6,2)"/"substr($1,1,4) " alle ore " substr($1,12,8), "\n", "Inizio validità:", substr($2,9,2)"/"substr($2,6,2)"/"substr($2,1,4) " alle ore " substr($2,12,8), "\n", "Termine validità",  substr($3,9,2) "/"substr($3,6,2)"/"substr($3,1,4) " alle ore " substr($3,12,8), "\n", "Avviso di criticità:", $9, "\n", "Avviso idrogeologico", $10, "\n", "Avviso temporali", $11, "\n", "Avviso idraulico", $12, "\n" }'  bollettino-oggi-comuni-latest.csv |awk '{$1=$1};1' > allerta_oggi_comune.txt

#dati comune di xxxyyy per domani
awk -F , '$5 == "xxxyyy" {print "Zona di validità, comune di:", $5, "\n", "Bollettino emesso il", substr($1,9,2)"/"substr($1,6,2)"/"substr($1,1,4) " alle ore " substr($1,12,8), "\n", "Inizio validità:", substr($2,9,2)"/"substr($2,6,2)"/"substr($2,1,4) " alle ore " substr($2,12,8), "\n", "Termine validità",  substr($3,9,2) "/"substr($3,6,2)"/"substr($3,1,4) " alle ore " substr($3,12,8), "\n", "Avviso di criticità:", $9, "\n", "Avviso idrogeologico", $10, "\n", "Avviso temporali", $11, "\n", "Avviso idraulico", $12, "\n" }'  bollettino-domani-comuni-latest.csv |awk '{$1=$1};1' > allerta_domani_comune.txt


#cerco occorrenze delle parole chiave ALLERTA GIALLA ARANCIONE ROSSA
 # if grep -Eq "GIALLA|ARANCIONE|ROSSA" allerta_oggi_zona.txt; then
    # cat allerta_oggi_zona.txt  >> alert.txt 
# else
	# echo "Nessuna allerta per oggi per la zona XXXYYYY"
    # fi 
	
 if grep -Eq "GIALLA|ARANCIONE|ROSSA" allerta_domani_zona.txt; then
    cat allerta_domani_zona.txt >> alert.txt
else
	echo "Nessuna allerta per domani per la zona XXXYYYY"
    fi    
	
 # if grep -Eq "GIALLA|ARANCIONE|ROSSA" allerta_oggi_comune.txt; then
    # cat allerta_oggi_comune.txt >> alert.txt
# else
	# echo "Nessuna allerta per oggi per il Comune di xxxyyy"
    # fi 

 if grep -Eq "GIALLA|ARANCIONE|ROSSA" allerta_domani_comune.txt; then
    cat allerta_domani_comune.txt >> alert.txt
else
	echo "Nessuna allerta per domani per il Comune di xxxyyy"
    fi 

#Invio il messaggio Telegram al gruppo

curl -s -X POST https://api.telegram.org/bot$TOKEN/sendMessage -d chat_id=$CHAT_ID --data-urlencode text@alert.txt > /dev/null

