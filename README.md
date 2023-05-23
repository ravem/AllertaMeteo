# AllertaMeteo
Questo script estrae i dati di allerta e/o criticità idrogeologica pubblicati dal Dipartimento di Protezione Civile, li invia via Telegram e li pubblica su una pagina web.
Lo script va configurato nei parametri relativi al bot telegram, ai percorsi relativi al server web e nelle zone di allertamento e comune di interesse.


I dati utilizzati dallo script sono estratti dalla versione processata e salvata come csv pubblicata qui: https://github.com/opendatasicilia/DPC-bollettini-criticita-idrogeologica-idraulica grazie al lavoro di https://opendatasicilia.it/

Il sistema è sperimentale e NON va usato che a scopo informativo, le informazioni ufficiali per quanto riguarda gli allerta sono quelle emanate dal Dipartimento e/o dalle regioni, consultabili qui: https://rischi.protezionecivile.gov.it/it/meteo-idro/allertamento/

#TODO riscrivere il codice processando direttamente il file pubblicato dal Dipartimento estraendo in dati di interesse e pubblicandoli in maniera grafica in modo da favorirne la leggibilità
