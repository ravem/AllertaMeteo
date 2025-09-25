### Allerta Meteo
Questo script estrae i dati di allerta e/o criticità idrogeologica pubblicati dal Dipartimento di Protezione Civile, li invia via Telegram e li pubblica su una pagina web.
Lo script va configurato nei parametri relativi al bot telegram, ai percorsi relativi al server web e nelle zone di allertamento e comune di interesse.

Lo script è stato completamente rifatto, in python, basandosi sul lavoro di https://github.com/opendatasicilia/DPC-bollettini-criticita-idrogeologica-idraulica.
I dati vengono scaricati direttamente dal repository del Dipartimento di Protezione Civile, vengono processati estraendo quelli rilevanti per la zona il comune di interesse.
Nel messaggio Telegram e nella pagina web è stata aggiunta una una formattazione con indicatori colorati che faciliti la lettura.

#Non sono un programmatore, ho largamente sfruttato l'aiuto dell'AI per creare lo script, per cui ogni suggerimento è benvenuto.

NOTA RELATIVA AI DATI RIPORTATI (dal readme contenuto nei bollettini emessi dal Dipartimento)

*Il Bollettino di criticità nazionale/allerta è una sintesi delle valutazioni di criticità emesse dai Centri Funzionali Decentrati delle Regioni e Province Autonome. La valutazione viene effettuata in modo indipendente per tre rischi:*   
*Rischio Idrogeologico*   
*Rischio Temporali*   
*Rischio Idraulico*           
*La previsione di criticità/allerta per il rischio temporali è stata introdotta con le Indicazioni operative del 10 febbraio 2016.*   
*Ogni rischio ha i seguenti livelli di criticità/allerta:*   
*Assenza di Criticità/Nessuna Allerta*   
*Ordinaria Criticità/Allerta Gialla*   
*Moderata Criticità/Allerta arancione*   
*Elevata Criticità/Allerta rossa*   
*Tranne temporali che NON ha il livello di criticità Elevata/Allerta rossa.*   
*Anche la corrispondenza tra i livelli di criticità, previsti dalla Direttiva del Presidente del Consiglio dei Ministri del 27 febbraio 2004, e i livelli di allerta è definita nelle Indicazioni operative del 10 febbraio 2016. Nello stesso documento è stato stabilito che il termine “allerta” sia associato ai codici colore (giallo, arancione, rosso) corrispondenti ai livelli di criticità (ordinaria, moderata, elevata).*   
*Per il rischio temporali non è prevista la criticità/allerta rossa perché, in questo caso, tali fenomeni sono associati a condizioni meteo perturbate intense e diffuse che già caratterizzano lo scenario di criticità/allerta idrogeologica rossa. Anche gli effetti e i danni prodotti sono gli stessi.*
