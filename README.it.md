# Carburanti Economici Italia ⛽🇮🇹

[![Add to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ivhazu&repository=carburanti_economici_ha&category=integration)
[![Add integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=carburanti_economici)

[![Marketplace / HACS](https://img.shields.io/badge/Marketplace%20%2F%20HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/v/release/ivhazu/carburanti_economici_ha)](https://github.com/ivhazu/carburanti_economici_ha/releases)
[![Validate](https://github.com/ivhazu/carburanti_economici_ha/actions/workflows/validate.yml/badge.svg)](https://github.com/ivhazu/carburanti_economici_ha/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.7%2B-blue.svg)](https://www.home-assistant.io/)
[![Made with Claude](https://img.shields.io/badge/Made%20with-Claude-8A63D2.svg)](https://claude.ai)

🇬🇧 **[Read in English → README.md](README.md)**

| Configurazione | Lovelace card |
|:-:|:-:|
| ![Config](images/screenshot_config.png) | ![Card](images/screenshot_card.png) |

---

**Carburanti Economici Italia** è una integrazione per Home Assistant che trova i distributori di carburante più economici vicino a una zona o a un device tracker, usando i dati ufficiali del Ministero delle Imprese e del Made in Italy (MIMIT).

> 🤖 Questa integrazione è stata sviluppata interamente da [Claude](https://claude.ai) (Anthropic). Idea, test e pubblicazione sono di [@ivhazu](https://github.com/ivhazu).

## ✨ Funzionalità

- 📍 **Zone e device tracker**: cerca vicino a qualsiasi zona HA o segui la posizione di un veicolo o di una persona
- ⛽ **Benzina, Diesel (Gasolio) e GPL**, selezionabili singolarmente
- 🏆 **Fino a 5 distributori** per carburante, con entità separate (1°, 2°, 3°…)
- 📏 **Raggio** da 1 a 50 km e **filtro anzianità prezzi** (0 = solo prezzi recenti)
- 📥 **Sorgente CSV open data** (consigliata): un solo download al giorno, senza errori 429; ripiega sull'API se il CSV non è disponibile
- 🕒 **Aggiornamento automatico** a un orario scelto, ogni N giorni, oppure **solo manuale**
- 🔄 **Pulsante di aggiornamento** per ogni istanza
- 🗺️ **Card Lovelace inclusa**: lista prezzi e mappa con pin numerati, aggiornamento automatico della vista e pulsante di refresh
- 🧹 **Pulizia automatica** di dispositivi ed entità quando riduci carburanti o distributori
- 🔧 Tutto configurabile dalla UI, nessun YAML

## 📥 Installazione

**Marketplace (Home Assistant 2026.11 o successivo)**

1. Premi il pulsante **Add to HACS** in cima a questa pagina (dalla 2026.11 apre il Marketplace), oppure vai in *Impostazioni → Marketplace*, premi **Add from link** e inserisci `ivhazu/carburanti_economici_ha` (per aggiungere un repository personalizzato serve collegare un account GitHub)
2. Apri **Carburanti Economici Italia** e premi **Install**. Riavvia Home Assistant solo se te lo chiede
3. Premi **Add integration** in cima a questa pagina, oppure *Impostazioni → Dispositivi e servizi → Aggiungi integrazione*

**HACS (Home Assistant 2026.10 o precedente)**

1. In HACS → menu ⋮ → *Repository personalizzati* aggiungi `https://github.com/ivhazu/carburanti_economici_ha` come **Integrazione**
2. Scarica **Carburanti Economici Italia** e riavvia Home Assistant
3. Aggiungi l'integrazione come sopra

> L'integrazione non è (ancora) nel catalogo predefinito: si aggiunge come repository personalizzato. Su Home Assistant 2026.11+ HACS non si può installare, perché lo sostituisce il Marketplace.

**Manuale**: copia `custom_components/carburanti_economici/` in `config/custom_components/` e riavvia.

## ⚙️ Configurazione

| Campo | Descrizione | Default |
|-------|-------------|---------|
| Tipo sorgente | Zona o device tracker | Zona |
| Zona / Device tracker | Da dove prendere le coordinate | — |
| Raggio (km) | Raggio di ricerca | 10 |
| N° distributori | Quanti distributori importare (1-5) | 1 |
| Anzianità prezzi (giorni) | Scarta prezzi più vecchi; 0 = solo oggi (con il CSV: oggi e ieri) | 7 |
| Sorgente dati | CSV open data (con ripiego su API) oppure solo API | CSV |
| Modalità aggiornamento | Automatico giornaliero o solo manuale | Automatico |
| Orario / ogni N giorni | Quando aggiornare. Con il CSV scegli dopo le 8:00 | 08:30 / 1 |
| Benzina, Diesel, GPL | Carburanti da cercare | Benzina, Diesel |

Ogni zona o device tracker si può configurare una sola volta. Le installazioni create prima della v1.5 restano sull'API finché non cambi la *Sorgente dati* dalle opzioni.

## 📊 Dati

- **CSV open data MIMIT** (anagrafica impianti e prezzi, aggiornato ogni mattina): una sola richiesta al giorno. I prezzi possono avere fino a un giorno di ritardo.
- **API `carburanti.mise.gov.it`**: dati più freschi, ma una chiamata per ogni distributore, con limiti (errore 429). L'integrazione ritenta con attese crescenti.

Prezzi **self-service** ove disponibili, altrimenti prezzo servito. Dati forniti dai gestori ai sensi della Legge 99/2009.

## 🔧 Entità

Per ogni *zona/tracker + carburante + posizione* vengono create 5 entità:

| Entità | Descrizione |
|--------|-------------|
| `sensor.distributore_1deg_benzina_home_prezzo` | Prezzo (€/L) |
| `sensor.distributore_1deg_benzina_home_nome` | Nome del distributore |
| `sensor.distributore_1deg_benzina_home_indirizzo` | Indirizzo (con `latitude`, `longitude` e immagine del pin) |
| `sensor.distributore_1deg_benzina_home_marchio` | Marchio |
| `sensor.distributore_1deg_benzina_home_aggiornamento` | Data di aggiornamento del prezzo |
| `button.aggiorna_carburanti_home` | Aggiorna subito i dati |

Il sensore `_prezzo` di rango 1 espone anche attributi diagnostici: `last_api_call`, `data_source` (sorgente realmente usata), `last_error` (ultimo errore) e `warnings` (ad esempio "2/5 distributori recenti: aumenta raggio o anzianità").

## 🗺️ Card Lovelace

La card viene registrata automaticamente. Se non compare tra le schede, aggiungila in *Impostazioni → Dashboard → Risorse* con URL `/carburanti_economici/carburanti-economici-card.js` e tipo **Modulo JavaScript**.

```yaml
type: custom:carburanti-economici-card
entities:
  - sensor.distributore_1deg_benzina_home_prezzo
  - sensor.distributore_2deg_benzina_home_prezzo
  - sensor.distributore_3deg_benzina_home_prezzo
```

Mostra bandiera, zona e carburante, la lista con marchio, prezzo e indirizzo, la mappa (card `map` nativa) e la data dell'ultimo aggiornamento con il pulsante di refresh. Si aggiorna da sola e su schermi stretti la mappa passa sotto la lista. L'editor grafico è disponibile dalla UI.

**Pin della mappa.** Di default il pin è un badge neutro con la sigla del marchio e la posizione in classifica. Per usare i **loghi** dei marchi, copia le immagini in `config/www/carburanti_economici/logos/` chiamandole come il marchio in minuscolo con `_` al posto di spazi e simboli: `esso.png`, `q8.png`, `agip_eni.png`, `api_ip.png`, `pompe_bianche.png` (il nome del marchio è nello stato del sensore `_marchio`). Formati: png, svg, webp, jpg. Se la cartella `www` non esisteva, riavvia una volta Home Assistant. I loghi non sono inclusi nel repository perché appartengono ai rispettivi proprietari.

## 📋 Requisiti e problemi noti

- Home Assistant **2024.7** o superiore, connessione internet, almeno una zona o un device tracker con coordinate
- I prezzi dipendono da quando i gestori li comunicano: usa il filtro anzianità
- La registrazione automatica della risorsa Lovelace può non riuscire su alcune versioni di HA (workaround sopra)
- La sorgente CSV è recente: se qualcosa non torna, controlla `data_source`, `last_error` e `warnings`, e apri una issue

## 🤝 Contributi e licenza

Issue e PR sono benvenute. Licenza MIT, vedi [LICENSE](LICENSE). Grazie a **MIMIT** per i dati aperti, a **Claude** per lo sviluppo e a **@ivhazu** per test e pubblicazione.
