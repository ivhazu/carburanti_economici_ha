"""Constants for Carburanti Economici Italia."""

DOMAIN = "carburanti_economici"

CONF_ZONE = "zone"
CONF_RADIUS = "radius"
CONF_FUEL_TYPES = "fuel_types"
CONF_MAX_AGE_DAYS = "max_age_days"
CONF_NUM_STATIONS = "num_stations"
CONF_SOURCE_TYPE = "source_type"
CONF_SOURCE_ENTITY = "source_entity"
CONF_UPDATE_MODE = "update_mode"      # "scheduled" or "manual"
CONF_UPDATE_TIME = "update_time"      # "HH:MM"
CONF_UPDATE_DAYS = "update_days"      # every N days
CONF_DATA_SOURCE = "data_source"      # "csv" or "api"

DATA_SOURCE_CSV = "csv"
DATA_SOURCE_API = "api"

SOURCE_TYPE_ZONE = "zone"
SOURCE_TYPE_TRACKER = "device_tracker"

UPDATE_MODE_SCHEDULED = "scheduled"
UPDATE_MODE_MANUAL = "manual"

FUEL_BENZINA = "benzina"
FUEL_DIESEL = "diesel"
FUEL_GPL = "gpl"

FUEL_TYPES = {
    FUEL_BENZINA: {
        "name": "Benzina",
        "api_code": "1-x",
        "fuel_name_api": "Benzina",
        "fuel_name_csv": "benzina",
        "icon": "mdi:gas-station",
    },
    FUEL_DIESEL: {
        "name": "Diesel (Gasolio)",
        "api_code": "2-x",
        "fuel_name_api": "Gasolio",
        "fuel_name_csv": "gasolio",
        "icon": "mdi:gas-station-in-use",
    },
    FUEL_GPL: {
        "name": "GPL",
        "api_code": "4-x",
        "fuel_name_api": "G.P.L.",
        "fuel_name_csv": "gpl",
        "icon": "mdi:gas-cylinder",
    },
}

STATION_ORDINALS = {1: "1°", 2: "2°", 3: "3°", 4: "4°", 5: "5°"}

API_SEARCH_URL = "https://carburanti.mise.gov.it/ospzApi/search/zone"
API_REGISTRY_URL = "https://carburanti.mise.gov.it/ospzApi/registry/servicearea/{}"

DEFAULT_RADIUS = 10
DEFAULT_MAX_AGE_DAYS = 7
DEFAULT_NUM_STATIONS = 1
DEFAULT_UPDATE_MODE = UPDATE_MODE_SCHEDULED
DEFAULT_UPDATE_TIME = "08:30"  # il CSV MIMIT è pubblicato alle 8:00
DEFAULT_UPDATE_DAYS = 1
DEFAULT_DATA_SOURCE = DATA_SOURCE_CSV  # solo per le NUOVE configurazioni
API_CALL_DELAY = 2  # seconds between consecutive API calls
API_MAX_RETRIES = 3          # tentativi per chiamata in caso di 429/5xx
API_RETRY_BASE_DELAY = 5     # secondi, raddoppia a ogni tentativo

CSV_PRICES_URL = "https://www.mimit.gov.it/images/exportCSV/prezzo_alle_8.csv"
CSV_STATIONS_URL = "https://www.mimit.gov.it/images/exportCSV/anagrafica_impianti_attivi.csv"
CSV_TIMEOUT = 180
