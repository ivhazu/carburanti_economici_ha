"""Button platform for Carburanti Economici Italia — manual refresh."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CarburantiCoordinator
from .const import CONF_SOURCE_ENTITY, DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: CarburantiCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([CarburantiRefreshButton(coordinator, entry)])


class CarburantiRefreshButton(CoordinatorEntity, ButtonEntity):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        source_entity = entry.data[CONF_SOURCE_ENTITY]
        source_slug = source_entity.split(".")[-1].replace(".", "_")
        source_label = source_slug.replace("_", " ").title()
        self._attr_unique_id = f"{entry.entry_id}_refresh"
        self._attr_name = f"Aggiorna Carburanti {source_label}"
        self._attr_icon = "mdi:refresh"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self.coordinator.entry.entry_id}_control")},
            "name": "Carburanti Economici — Controllo",
            "manufacturer": "MIMIT / carburanti.mise.gov.it",
        }

    async def async_press(self):
        await self.coordinator.async_request_refresh()
