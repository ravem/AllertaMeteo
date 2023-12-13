### Allerta Meteo
Questo script estrae i dati di allerta e/o criticità idrogeologica pubblicati dal Dipartimento di Protezione Civile, li invia via Telegram e li pubblica su una pagina web.
Lo script va configurato nei parametri relativi al bot telegram, ai percorsi relativi al server web e nelle zone di allertamento e comune di interesse.


I dati utilizzati dallo script sono estratti dalla versione processata e salvata come csv pubblicata qui: https://github.com/opendatasicilia/DPC-bollettini-criticita-idrogeologica-idraulica grazie al lavoro di https://opendatasicilia.it/

Il sistema è sperimentale e NON va usato che a scopo informativo, le informazioni ufficiali per quanto riguarda gli allerta sono quelle emanate dal Dipartimento e/o dalle regioni, consultabili qui: https://rischi.protezionecivile.gov.it/it/meteo-idro/allertamento/

#TODO riscrivere il codice processando direttamente il file pubblicato dal Dipartimento estraendo in dati di interesse e pubblicandoli in maniera grafica in modo da favorirne la leggibilità




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
