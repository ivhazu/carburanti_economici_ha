"""Config flow for Carburanti Economici Italia."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    NumberSelector, NumberSelectorConfig, NumberSelectorMode,
    SelectOptionDict, SelectSelector, SelectSelectorConfig, SelectSelectorMode,
    TextSelector, TextSelectorConfig, TextSelectorType,
    BooleanSelector,
)

from .const import (
    CONF_FUEL_TYPES, CONF_MAX_AGE_DAYS, CONF_NUM_STATIONS,
    CONF_RADIUS, CONF_SOURCE_ENTITY, CONF_SOURCE_TYPE,
    CONF_UPDATE_DAYS, CONF_UPDATE_MODE, CONF_UPDATE_TIME,
    DEFAULT_MAX_AGE_DAYS, DEFAULT_NUM_STATIONS, DEFAULT_RADIUS,
    DEFAULT_UPDATE_DAYS, DEFAULT_UPDATE_MODE, DEFAULT_UPDATE_TIME,
    DOMAIN, FUEL_BENZINA, FUEL_DIESEL, FUEL_GPL, FUEL_TYPES,
    SOURCE_TYPE_TRACKER, SOURCE_TYPE_ZONE,
    UPDATE_MODE_MANUAL, UPDATE_MODE_SCHEDULED,
)


def _get_zone_options(hass: HomeAssistant) -> list[SelectOptionDict]:
    opts = []
    for eid in hass.states.async_entity_ids("zone"):
        s = hass.states.get(eid)
        name = (s.attributes.get("friendly_name") if s else None) or eid
        opts.append(SelectOptionDict(value=eid, label=f"📍 {name}"))
    return sorted(opts, key=lambda x: x["label"])


def _get_tracker_options(hass: HomeAssistant) -> list[SelectOptionDict]:
    opts = []
    for eid in hass.states.async_entity_ids("device_tracker"):
        s = hass.states.get(eid)
        name = (s.attributes.get("friendly_name") if s else None) or eid
        opts.append(SelectOptionDict(value=eid, label=f"🚗 {name}"))
    return sorted(opts, key=lambda x: x["label"])


def _build_schema(hass: HomeAssistant, defaults: dict | None = None) -> vol.Schema:
    d = defaults or {}
    all_sources = _get_zone_options(hass) + _get_tracker_options(hass)
    default_entity = d.get(CONF_SOURCE_ENTITY) or (all_sources[0]["value"] if all_sources else None)
    update_mode = d.get(CONF_UPDATE_MODE, DEFAULT_UPDATE_MODE)

    return vol.Schema({
        vol.Required(CONF_SOURCE_TYPE, default=d.get(CONF_SOURCE_TYPE, SOURCE_TYPE_ZONE)):
            SelectSelector(SelectSelectorConfig(options=[
                SelectOptionDict(value=SOURCE_TYPE_ZONE, label="Zona"),
                SelectOptionDict(value=SOURCE_TYPE_TRACKER, label="Device Tracker"),
            ], mode=SelectSelectorMode.DROPDOWN)),
        vol.Required(CONF_SOURCE_ENTITY, default=default_entity):
            SelectSelector(SelectSelectorConfig(options=all_sources, mode=SelectSelectorMode.DROPDOWN)),
        vol.Required(CONF_RADIUS, default=d.get(CONF_RADIUS, DEFAULT_RADIUS)):
            NumberSelector(NumberSelectorConfig(min=1, max=50, step=1, mode=NumberSelectorMode.BOX)),
        vol.Required(CONF_NUM_STATIONS, default=d.get(CONF_NUM_STATIONS, DEFAULT_NUM_STATIONS)):
            NumberSelector(NumberSelectorConfig(min=1, max=5, step=1, mode=NumberSelectorMode.BOX)),
        vol.Required(CONF_MAX_AGE_DAYS, default=d.get(CONF_MAX_AGE_DAYS, DEFAULT_MAX_AGE_DAYS)):
            NumberSelector(NumberSelectorConfig(min=0, max=90, step=1, mode=NumberSelectorMode.BOX)),
        vol.Required(CONF_UPDATE_MODE, default=update_mode):
            SelectSelector(SelectSelectorConfig(options=[
                SelectOptionDict(value=UPDATE_MODE_SCHEDULED, label="Aggiornamento automatico giornaliero"),
                SelectOptionDict(value=UPDATE_MODE_MANUAL, label="Solo aggiornamento manuale"),
            ], mode=SelectSelectorMode.DROPDOWN)),
        vol.Optional(CONF_UPDATE_TIME, default=d.get(CONF_UPDATE_TIME, DEFAULT_UPDATE_TIME)):
            TextSelector(TextSelectorConfig(type=TextSelectorType.TIME)),
        vol.Optional(CONF_UPDATE_DAYS, default=d.get(CONF_UPDATE_DAYS, DEFAULT_UPDATE_DAYS)):
            NumberSelector(NumberSelectorConfig(min=1, max=30, step=1, mode=NumberSelectorMode.BOX)),
        vol.Optional("fuel_benzina", default=d.get("fuel_benzina", True)): bool,
        vol.Optional("fuel_diesel", default=d.get("fuel_diesel", True)): bool,
        vol.Optional("GPL", default=d.get("GPL", False)): bool,
    })


def _extract(user_input: dict) -> dict:
    fuels = []
    if user_input.get("fuel_benzina"): fuels.append(FUEL_BENZINA)
    if user_input.get("fuel_diesel"): fuels.append(FUEL_DIESEL)
    if user_input.get("GPL"): fuels.append(FUEL_GPL)
    return {
        CONF_SOURCE_TYPE: user_input[CONF_SOURCE_TYPE],
        CONF_SOURCE_ENTITY: user_input[CONF_SOURCE_ENTITY],
        CONF_RADIUS: int(user_input[CONF_RADIUS]),
        CONF_NUM_STATIONS: int(user_input[CONF_NUM_STATIONS]),
        CONF_MAX_AGE_DAYS: int(user_input[CONF_MAX_AGE_DAYS]),
        CONF_UPDATE_MODE: user_input[CONF_UPDATE_MODE],
        CONF_UPDATE_TIME: user_input.get(CONF_UPDATE_TIME, DEFAULT_UPDATE_TIME),
        CONF_UPDATE_DAYS: int(user_input.get(CONF_UPDATE_DAYS, DEFAULT_UPDATE_DAYS)),
        CONF_FUEL_TYPES: fuels,
    }


class CarburantiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if not _get_zone_options(self.hass) and not _get_tracker_options(self.hass):
            return self.async_abort(reason="no_sources_found")

        if user_input is not None:
            data = _extract(user_input)
            if not data[CONF_FUEL_TYPES]:
                errors["base"] = "no_fuel_selected"
            else:
                s = self.hass.states.get(data[CONF_SOURCE_ENTITY])
                name = (s.attributes.get("friendly_name") if s else None) or data[CONF_SOURCE_ENTITY]
                fuels = " + ".join(FUEL_TYPES[f]["name"] for f in data[CONF_FUEL_TYPES])
                return self.async_create_entry(title=f"{name} — {fuels}", data=data)

        return self.async_show_form(step_id="user",
                                    data_schema=_build_schema(self.hass), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return CarburantiOptionsFlow(config_entry.entry_id)


class CarburantiOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry_id):
        self._entry_id = entry_id

    async def async_step_init(self, user_input=None):
        errors = {}
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        d = entry.data
        current_fuels = d.get(CONF_FUEL_TYPES, [])

        if user_input is not None:
            data = _extract(user_input)
            if not data[CONF_FUEL_TYPES]:
                errors["base"] = "no_fuel_selected"
            else:
                self.hass.config_entries.async_update_entry(entry, data=data)
                await self.hass.config_entries.async_reload(self._entry_id)
                return self.async_create_entry(title="", data={})

        defaults = {
            CONF_SOURCE_TYPE: d.get(CONF_SOURCE_TYPE, SOURCE_TYPE_ZONE),
            CONF_SOURCE_ENTITY: d.get(CONF_SOURCE_ENTITY),
            CONF_RADIUS: d.get(CONF_RADIUS, DEFAULT_RADIUS),
            CONF_NUM_STATIONS: d.get(CONF_NUM_STATIONS, DEFAULT_NUM_STATIONS),
            CONF_MAX_AGE_DAYS: d.get(CONF_MAX_AGE_DAYS, DEFAULT_MAX_AGE_DAYS),
            CONF_UPDATE_MODE: d.get(CONF_UPDATE_MODE, DEFAULT_UPDATE_MODE),
            CONF_UPDATE_TIME: d.get(CONF_UPDATE_TIME, DEFAULT_UPDATE_TIME),
            CONF_UPDATE_DAYS: d.get(CONF_UPDATE_DAYS, DEFAULT_UPDATE_DAYS),
            "fuel_benzina": FUEL_BENZINA in current_fuels,
            "fuel_diesel": FUEL_DIESEL in current_fuels,
            "GPL": FUEL_GPL in current_fuels,
        }
        return self.async_show_form(step_id="init",
                                    data_schema=_build_schema(self.hass, defaults), errors=errors)
