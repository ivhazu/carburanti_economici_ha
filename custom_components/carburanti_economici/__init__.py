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
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import csv_source
from .const import (
    API_CALL_DELAY,
    API_MAX_RETRIES,
    API_RETRY_BASE_DELAY,
    CONF_DATA_SOURCE,
    CSV_PRICES_URL,
    CSV_STATIONS_URL,
    CSV_TIMEOUT,
    DATA_SOURCE_API,
    DATA_SOURCE_CSV,
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
        self.last_api_call: datetime | None = None
        self.last_error: str | None = None
        self.data_source_used: str | None = None

        # Use a very long update_interval so async_request_refresh works
        # Actual scheduling is handled manually via async_track_time_change
        super().__init__(
            hass, _LOGGER, name=DOMAIN,
            update_interval=timedelta(days=365),
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
    def data_source(self) -> str:
        # le configurazioni esistenti (senza chiave) restano sull'API
        return self.entry.data.get(CONF_DATA_SOURCE, DATA_SOURCE_API)

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
        """Prezzo recente? Le date naive del MIMIT sono in ora italiana."""
        if not insert_date:
            return False
        try:
            dt = datetime.fromisoformat(insert_date)
        except (ValueError, TypeError):
            return False
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
        now = dt_util.now()
        if self.max_age_days == 0:
            return dt_util.as_local(dt).date() >= now.date()
        return dt >= now - timedelta(days=self.max_age_days)

    async def _async_update_data(self) -> dict:
        coords = self._get_coords()
        if coords is None:
            raise UpdateFailed(f"Source '{self.source_entity}' has no coordinates.")
        lat, lng = coords

        self.last_api_call = datetime.now(tz=timezone.utc)
        session = async_get_clientsession(self.hass)
        result: dict | None = None
        error: str | None = None

        if self.data_source == DATA_SOURCE_CSV:
            try:
                result = await self._update_from_csv(session, lat, lng)
                self.data_source_used = DATA_SOURCE_CSV
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Sorgente CSV non utilizzabile (%s): ripiego sull'API", err)
                error = f"CSV: {err}"

        if result is None:
            try:
                result = await self._update_from_api(session, lat, lng)
                self.data_source_used = DATA_SOURCE_API
            except Exception as err:  # noqa: BLE001
                error = f"{error + ' | ' if error else ''}API: {err}"
                result = None

        if result is None:
            self.last_error = error
            if self.data:
                # tengo gli ultimi dati buoni invece di rendere tutto "non disponibile"
                _LOGGER.error("Aggiornamento fallito, mantengo i dati precedenti: %s", error)
                return self.data
            raise UpdateFailed(error or "aggiornamento fallito")

        # carburanti falliti singolarmente: tengo i vecchi dati se ci sono
        failed = result.pop("_failed", {})
        for fuel_key, msg in failed.items():
            if self.data and self.data.get(fuel_key):
                result[fuel_key] = self.data[fuel_key]
            else:
                result.setdefault(fuel_key, [])
        notes = [error] if error else []  # CSV fallito ma API riuscita
        notes += [f"{k}: {v}" for k, v in failed.items()]
        self.last_error = "; ".join(notes) or None
        return result

    # ---------------------------------------------------------------- CSV
    async def _download(self, session, url: str) -> bytes:
        async with async_timeout(CSV_TIMEOUT):
            async with session.get(url) as resp:
                resp.raise_for_status()
                return await resp.read()

    async def _update_from_csv(self, session, lat, lng) -> dict:
        raw_st = await self._download(session, CSV_STATIONS_URL)
        stations = await self.hass.async_add_executor_job(
            csv_source.parse_stations_in_radius, raw_st, lat, lng, self.radius
        )
        if not stations:
            raise ValueError(f"nessun impianto entro {self.radius} km nell'anagrafica CSV")
        raw_pr = await self._download(session, CSV_PRICES_URL)
        fuel_names = {k: FUEL_TYPES[k]["fuel_name_csv"] for k in self.fuel_types}
        prices = await self.hass.async_add_executor_job(
            csv_source.parse_prices, raw_pr, set(stations), fuel_names
        )
        if not any(prices.values()):
            raise ValueError("nessun prezzo trovato nel CSV per gli impianti della zona")

        result: dict = {}
        for fuel_key in self.fuel_types:
            rows = sorted(prices[fuel_key].items(), key=lambda kv: kv[1]["price"])
            found = []
            for sid, p in rows:
                if len(found) >= self.num_stations:
                    break
                if not self._is_fresh(p["insert_date"]):
                    continue
                st = stations[sid]
                found.append({
                    "id": sid, "name": st["name"], "brand": st["brand"],
                    "address": st["address"], "price": p["price"],
                    "insert_date": p["insert_date"],
                    "latitude": st["latitude"], "longitude": st["longitude"],
                })
            if not found:
                _LOGGER.warning("No fresh stations for %s within %d km", fuel_key, self.radius)
            result[fuel_key] = found
        return result

    # ---------------------------------------------------------------- API
    async def _update_from_api(self, session, lat, lng) -> dict:
        result: dict = {}
        failed: dict = {}
        for fuel_idx, fuel_key in enumerate(self.fuel_types):
            fuel_info = FUEL_TYPES[fuel_key]
            try:
                if fuel_idx > 0:
                    await asyncio.sleep(API_CALL_DELAY)
                station_tuples = await self._fetch_sorted_ids(
                    session, lat, lng, fuel_info["api_code"]
                )
                stations = []
                for station_id, s_lat, s_lng in station_tuples:
                    if len(stations) >= self.num_stations:
                        break
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
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Error fetching %s: %s", fuel_key, err)
                failed[fuel_key] = str(err) or type(err).__name__
        if failed and len(failed) == len(self.fuel_types):
            raise UpdateFailed("; ".join(f"{k}: {v}" for k, v in failed.items()))
        result["_failed"] = failed
        return result

    async def _request_json(self, session, method: str, url: str, **kwargs):
        """GET/POST con retry e backoff su 429/5xx."""
        delay = API_RETRY_BASE_DELAY
        for attempt in range(1, API_MAX_RETRIES + 1):
            try:
                async with async_timeout(60):
                    async with session.request(method, url, **kwargs) as resp:
                        if resp.status in (429, 500, 502, 503, 504) and attempt < API_MAX_RETRIES:
                            retry_after = resp.headers.get("Retry-After", "")
                            wait = int(retry_after) if retry_after.isdigit() else delay
                            _LOGGER.debug("HTTP %s da %s, riprovo tra %ss", resp.status, url, wait)
                        else:
                            resp.raise_for_status()
                            return await resp.json()
            except (aiohttp.ClientConnectionError, asyncio.TimeoutError):
                if attempt == API_MAX_RETRIES:
                    raise
                wait = delay
            await asyncio.sleep(wait)
            delay *= 2
        raise RuntimeError("retry esauriti")

    async def _fetch_sorted_ids(self, session, lat, lng, api_code):
        payload = {
            "points": [{"lat": lat, "lng": lng}],
            "radius": self.radius,
            "fuelType": api_code,
            "priceOrder": "asc",
        }
        data = await self._request_json(
            session, "POST", API_SEARCH_URL, json=payload,
            headers={"Content-Type": "application/json"},
        )
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
        data = await self._request_json(session, "GET", url)
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
