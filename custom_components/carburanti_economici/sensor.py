"""Sensor platform for Carburanti Economici Italia."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_EURO
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CarburantiCoordinator
from .const import CONF_FUEL_TYPES, CONF_SOURCE_ENTITY, DOMAIN, FUEL_TYPES, STATION_ORDINALS

_LOGGER = logging.getLogger(__name__)

# Sensor type suffixes — used both for entity_id and friendly name
SENSOR_SUFFIXES = {
    "prezzo":        "Prezzo",
    "nome":          "Nome",
    "indirizzo":     "Indirizzo",
    "marchio":       "Marchio",
    "aggiornamento": "Aggiornamento",
}


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: CarburantiCoordinator = hass.data[DOMAIN][entry.entry_id]
    fuel_types = entry.data[CONF_FUEL_TYPES]
    source_entity = entry.data[CONF_SOURCE_ENTITY]
    source_slug = source_entity.split(".")[-1]
    num_stations = coordinator.num_stations

    entities = []
    for fuel_key in fuel_types:
        for rank in range(1, num_stations + 1):
            ordinal = STATION_ORDINALS.get(rank, f"{rank}°")
            # entity_id base: distributore_1deg_benzina_home
            slug_base = f"distributore_{ordinal.replace('°','deg')}_{fuel_key}_{source_slug}"
            entities.extend([
                CarburantiPriceSensor(coordinator, entry, fuel_key, source_slug, rank, ordinal, slug_base),
                CarburantiNameSensor(coordinator, entry, fuel_key, source_slug, rank, ordinal, slug_base),
                CarburantiAddressSensor(coordinator, entry, fuel_key, source_slug, rank, ordinal, slug_base),
                CarburantiBrandSensor(coordinator, entry, fuel_key, source_slug, rank, ordinal, slug_base),
                CarburantiUpdateSensor(coordinator, entry, fuel_key, source_slug, rank, ordinal, slug_base),
            ])
    async_add_entities(entities)


class CarburantiBaseSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry, fuel_key, source_slug, rank, ordinal, slug_base, sensor_type):
        super().__init__(coordinator)
        self._fuel_key = fuel_key
        self._source_slug = source_slug
        self._rank = rank
        self._ordinal = ordinal
        self._sensor_type = sensor_type
        self._entry_id = entry.entry_id

        # Friendly name: "Distributore 1° Benzina Home Prezzo"
        fuel_label = FUEL_TYPES[fuel_key]["name"]
        source_label = source_slug.replace("_", " ").title()
        suffix_label = SENSOR_SUFFIXES.get(sensor_type, sensor_type.title())
        self._attr_name = f"Distributore {ordinal} {fuel_label} {source_label} {suffix_label}"

        # unique_id based on entry + type
        self._attr_unique_id = f"{entry.entry_id}_{fuel_key}_{rank}_{sensor_type}"

        # Force entity_id: sensor.distributore_1deg_benzina_home_prezzo
        self.entity_id = f"sensor.{slug_base}_{sensor_type}"

    @property
    def _station_data(self):
        if self.coordinator.data is None:
            return None
        stations = self.coordinator.data.get(self._fuel_key, [])
        return stations[self._rank - 1] if self._rank <= len(stations) else None

    @property
    def available(self):
        return self.coordinator.last_update_success and self._station_data is not None

    @property
    def extra_state_attributes(self):
        return {}

    @property
    def device_info(self):
        source_label = self._source_slug.replace("_", " ").title()
        fuel_label = FUEL_TYPES[self._fuel_key]["name"]
        return {
            "identifiers": {(DOMAIN, f"{self._entry_id}_{self._fuel_key}_{self._rank}")},
            "name": f"{self._ordinal} Distributore {fuel_label} — {source_label}",
            "manufacturer": "MIMIT / carburanti.mise.gov.it",
            "model": fuel_label,
        }


class CarburantiPriceSensor(CarburantiBaseSensor):
    def __init__(self, coordinator, entry, fuel_key, source_slug, rank, ordinal, slug_base):
        super().__init__(coordinator, entry, fuel_key, source_slug, rank, ordinal, slug_base, "prezzo")
        self._attr_icon = FUEL_TYPES[fuel_key]["icon"]
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_native_unit_of_measurement = f"{CURRENCY_EURO}/L"

    @property
    def native_value(self):
        data = self._station_data
        return data["price"] if data else None


class CarburantiNameSensor(CarburantiBaseSensor):
    def __init__(self, coordinator, entry, fuel_key, source_slug, rank, ordinal, slug_base):
        super().__init__(coordinator, entry, fuel_key, source_slug, rank, ordinal, slug_base, "nome")
        self._attr_icon = "mdi:store-marker"

    @property
    def native_value(self):
        data = self._station_data
        return data["name"] if data else None


class CarburantiAddressSensor(CarburantiBaseSensor):
    """Address sensor — exposes latitude and longitude as attributes."""

    def __init__(self, coordinator, entry, fuel_key, source_slug, rank, ordinal, slug_base):
        super().__init__(coordinator, entry, fuel_key, source_slug, rank, ordinal, slug_base, "indirizzo")
        self._attr_icon = "mdi:map-marker"

    @property
    def native_value(self):
        data = self._station_data
        return data["address"] if data else None

    @property
    def extra_state_attributes(self):
        data = self._station_data
        if not data:
            return {}
        attrs = {}
        if data.get("latitude") is not None:
            attrs["latitude"] = data["latitude"]
        if data.get("longitude") is not None:
            attrs["longitude"] = data["longitude"]
        return attrs


class CarburantiBrandSensor(CarburantiBaseSensor):
    def __init__(self, coordinator, entry, fuel_key, source_slug, rank, ordinal, slug_base):
        super().__init__(coordinator, entry, fuel_key, source_slug, rank, ordinal, slug_base, "marchio")
        self._attr_icon = "mdi:fuel"

    @property
    def native_value(self):
        data = self._station_data
        return data["brand"] if data else None


class CarburantiUpdateSensor(CarburantiBaseSensor):
    def __init__(self, coordinator, entry, fuel_key, source_slug, rank, ordinal, slug_base):
        super().__init__(coordinator, entry, fuel_key, source_slug, rank, ordinal, slug_base, "aggiornamento")
        self._attr_icon = "mdi:update"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        data = self._station_data
        if not data or not data.get("insert_date"):
            return None
        try:
            dt = datetime.fromisoformat(data["insert_date"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            return None
