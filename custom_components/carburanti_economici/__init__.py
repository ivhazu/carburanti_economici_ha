"""Carburanti Economici Italia integration."""
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import aiohttp

if sys.version_info >= (3, 11):
    from asyncio import timeout as async_timeout
else:
    from async_timeout import timeout as async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_CALL_DELAY,
    API_REGISTRY_URL,
    API_SEARCH_URL,
    CONF_FUEL_TYPES,
    CONF_MAX_AGE_DAYS,
    CONF_NUM_STATIONS,
    CONF_RADIUS,
    CONF_SOURCE_ENTITY,
    CONF_SOURCE_TYPE,
    CONF_UPDATE_DAYS,
    CONF_UPDATE_MODE,
    CONF_UPDATE_TIME,
    DEFAULT_MAX_AGE_DAYS,
    DEFAULT_NUM_STATIONS,
    DEFAULT_UPDATE_DAYS,
    DEFAULT_UPDATE_MODE,
    DEFAULT_UPDATE_TIME,
    DOMAIN,
    FUEL_TYPES,
    SOURCE_TYPE_TRACKER,
    UPDATE_MODE_MANUAL,
    UPDATE_MODE_SCHEDULED,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR, Platform.BUTTON]

CARD_JS_PATH = Path(__file__).parent / "www" / "carburanti-economici-card.js"
CARD_URL = f"/{DOMAIN}/carburanti-economici-card.js"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register static path for the card."""
    if CARD_JS_PATH.exists():
        from homeassistant.components.http import StaticPathConfig
        await hass.http.async_register_static_paths([
            StaticPathConfig(CARD_URL, str(CARD_JS_PATH), cache_headers=False)
        ])
        _LOGGER.debug("Registered card static path at %s", CARD_URL)
    return True


async def _async_register_lovelace_resource(hass: HomeAssistant) -> None:
    """Add the card JS as a Lovelace resource if not already registered."""
    try:
        lovelace_data = hass.data.get("lovelace")
        if lovelace_data is None:
            _LOGGER.debug("Lovelace not yet initialized, skipping resource registration")
            return

        resources = getattr(lovelace_data, "resources", None)
        if resources is None:
            raise ValueError("Could not access lovelace resources")

        await resources.async_load()

        for item in resources.async_items():
            if CARD_URL in item.get("url", ""):
                _LOGGER.debug("Lovelace resource already registered: %s", CARD_URL)
                return

        await resources.async_create_item({
            "res_type": "module",
            "url": CARD_URL,
        })
        _LOGGER.info("Auto-registered Lovelace resource: %s", CARD_URL)

    except Exception as err:
        _LOGGER.warning(
            "Could not auto-register Lovelace resource %s: %s. "
            "Please add it manually in Settings → Dashboard → Resources.",
            CARD_URL, err
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Carburanti Economici from a config entry."""
    coordinator = CarburantiCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await _async_register_lovelace_resource(hass)

    # Schedule daily update if mode is scheduled
    coordinator.async_setup_schedule()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: CarburantiCoordinator = hass.data[DOMAIN].get(entry.entry_id)
    if coordinator:
        coordinator.async_cancel_schedule()
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class CarburantiCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch cheapest fuel station data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self._unsub_schedule = None
        self._last_update_date: datetime | None = None

        # No automatic update_interval — we handle scheduling manually
        super().__init__(
            hass, _LOGGER, name=DOMAIN,
            update_interval=None,
        )

    def async_setup_schedule(self) -> None:
        """Set up the daily scheduled update if mode is scheduled."""
        if self.update_mode == UPDATE_MODE_MANUAL:
            _LOGGER.debug("Manual update mode — no schedule set")
            return

        update_time = self.entry.data.get(CONF_UPDATE_TIME, DEFAULT_UPDATE_TIME)
        try:
            t = time.fromisoformat(update_time)
        except ValueError:
            t = time(7, 0)

        _LOGGER.debug("Scheduling daily update at %s", t)
        self._unsub_schedule = async_track_time_change(
            self.hass,
            self._async_scheduled_update,
            hour=t.hour,
            minute=t.minute,
            second=0,
        )

    def async_cancel_schedule(self) -> None:
        """Cancel the scheduled update."""
        if self._unsub_schedule:
            self._unsub_schedule()
            self._unsub_schedule = None

    async def _async_scheduled_update(self, now: datetime) -> None:
        """Called by time tracker — check if we should update today."""
        update_days = self.entry.data.get(CONF_UPDATE_DAYS, DEFAULT_UPDATE_DAYS)
        if update_days > 1 and self._last_update_date is not None:
            days_since = (now.date() - self._last_update_date.date()).days
            if days_since < update_days:
                _LOGGER.debug(
                    "Skipping update: only %d days since last update (every %d days)",
                    days_since, update_days
                )
                return

        _LOGGER.debug("Scheduled update triggered at %s", now)
        self._last_update_date = now
        await self.async_request_refresh()

    @property
    def update_mode(self) -> str:
        return self.entry.data.get(CONF_UPDATE_MODE, DEFAULT_UPDATE_MODE)

    @property
    def source_entity(self) -> str:
        return self.entry.data[CONF_SOURCE_ENTITY]

    @property
    def source_type(self) -> str:
        return self.entry.data[CONF_SOURCE_TYPE]

    @property
    def radius(self) -> int:
        return self.entry.data[CONF_RADIUS]

    @property
    def fuel_types(self) -> list[str]:
        return self.entry.data[CONF_FUEL_TYPES]

    @property
    def max_age_days(self) -> int:
        return self.entry.data.get(CONF_MAX_AGE_DAYS, DEFAULT_MAX_AGE_DAYS)

    @property
    def num_stations(self) -> int:
        return self.entry.data.get(CONF_NUM_STATIONS, DEFAULT_NUM_STATIONS)

    def _get_coords(self) -> tuple[float, float] | None:
        state = self.hass.states.get(self.source_entity)
        if state is None:
            return None
        lat = state.attributes.get("latitude")
        lng = state.attributes.get("longitude")
        if lat is None or lng is None:
            if self.source_type == SOURCE_TYPE_TRACKER:
                _LOGGER.warning("Device tracker '%s' has no coordinates (state: %s)",
                                self.source_entity, state.state)
            return None
        return float(lat), float(lng)

    def _is_fresh(self, insert_date: str | None) -> bool:
        if not insert_date:
            return False
        try:
            dt = datetime.fromisoformat(insert_date)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(tz=timezone.utc)
            if self.max_age_days == 0:
                return dt.date() >= now.date()
            return dt >= now - timedelta(days=self.max_age_days)
        except (ValueError, TypeError):
            return False

    async def _async_update_data(self) -> dict:
        coords = self._get_coords()
        if coords is None:
            raise UpdateFailed(f"Source '{self.source_entity}' has no coordinates.")
        lat, lng = coords

        result = {}
        async with aiohttp.ClientSession() as session:
            for fuel_idx, fuel_key in enumerate(self.fuel_types):
                fuel_info = FUEL_TYPES[fuel_key]
                try:
                    # Delay between fuel types
                    if fuel_idx > 0:
                        await asyncio.sleep(API_CALL_DELAY)

                    station_tuples = await self._fetch_sorted_ids(
                        session, lat, lng, fuel_info["api_code"]
                    )
                    stations = []
                    for station_id, s_lat, s_lng in station_tuples:
                        if len(stations) >= self.num_stations:
                            break
                        # Delay between registry calls
                        if stations:
                            await asyncio.sleep(API_CALL_DELAY)
                        metadata = await self._fetch_station_metadata(
                            session, station_id, fuel_info["fuel_name_api"]
                        )
                        if self._is_fresh(metadata.get("insert_date")):
                            metadata["latitude"] = s_lat
                            metadata["longitude"] = s_lng
                            stations.append({"id": station_id, **metadata})
                        else:
                            _LOGGER.debug("Skipping station %s: price too old (%s)",
                                          station_id, metadata.get("insert_date"))
                    if not stations:
                        _LOGGER.warning("No fresh stations for %s within %d km",
                                        fuel_key, self.radius)
                    result[fuel_key] = stations
                except Exception as err:
                    _LOGGER.warning("Error fetching %s: %s", fuel_key, err)
                    result[fuel_key] = []
        return result

    async def _fetch_sorted_ids(self, session, lat, lng, api_code):
        payload = {
            "points": [{"lat": lat, "lng": lng}],
            "radius": self.radius,
            "fuelType": api_code,
            "priceOrder": "asc",
        }
        async with async_timeout(60):
            async with session.post(
                API_SEARCH_URL, json=payload,
                headers={"Content-Type": "application/json"}
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
        results = data.get("results", [])
        out = []
        for r in results:
            if not r.get("id"):
                continue
            rlat = (r.get("lat") or r.get("latitude") or r.get("latitudine") or
                    (r.get("location") or {}).get("lat"))
            rlng = (r.get("lng") or r.get("longitude") or r.get("longitudine") or
                    (r.get("location") or {}).get("lng"))
            out.append((str(r["id"]), rlat, rlng))
        return out

    async def _fetch_station_metadata(self, session, station_id, fuel_name):
        url = API_REGISTRY_URL.format(station_id)
        async with async_timeout(60):
            async with session.get(url) as resp:
                resp.raise_for_status()
                data = await resp.json()
        fuels = data.get("fuels", [])
        price = None
        insert_date = None
        for is_self in (True, False):
            match = next(
                (f for f in fuels
                 if f.get("name") == fuel_name and f.get("isSelf") is is_self),
                None,
            )
            if match:
                price = float(match.get("price", 0))
                insert_date = match.get("insertDate")
                break
        return {
            "name": data.get("name"),
            "brand": data.get("brand"),
            "address": data.get("address"),
            "price": price,
            "insert_date": insert_date,
        }
