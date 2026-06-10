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
        "icon": "mdi:gas-station",
    },
    FUEL_DIESEL: {
        "name": "Diesel (Gasolio)",
        "api_code": "2-x",
        "fuel_name_api": "Gasolio",
        "icon": "mdi:gas-station-in-use",
    },
    FUEL_GPL: {
        "name": "GPL",
        "api_code": "4-x",
        "fuel_name_api": "G.P.L.",
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
DEFAULT_UPDATE_TIME = "07:00"
DEFAULT_UPDATE_DAYS = 1
API_CALL_DELAY = 2  # seconds between consecutive API calls
