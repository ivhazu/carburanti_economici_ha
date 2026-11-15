"""Parser dei CSV open data MIMIT (anagrafica impianti + prezzi praticati).

Funzioni pure, senza dipendenze da Home Assistant, eseguibili in executor.
Il parser è volutamente tollerante: cerca la riga di intestazione per nome
(la prima riga del file MIMIT è "Estrazione del ..."), riconosce da solo il
separatore e accetta alias dei nomi colonna.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Iterable

# Nomi colonna normalizzati (minuscolo, senza spazi/underscore/punti)
_ID = ("idimpianto",)
_BRAND = ("bandiera",)
_NAME = ("nomeimpianto", "gestore")
_ADDR = ("indirizzo",)
_CITY = ("comune",)
_PROV = ("provincia",)
_LAT = ("latitudine", "lat")
_LNG = ("longitudine", "lng", "lon")
_FUEL = ("desccarburante", "carburante")
_PRICE = ("prezzo",)
_SELF = ("isself", "self")
_DATE = ("dtcomu", "datacomunicazione", "dtcomunicazione")

_DATE_FORMATS = ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%dT%H:%M:%S",
                 "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d")


def norm(text: str) -> str:
    return "".join(ch for ch in (text or "").lower() if ch.isalnum())


def decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _split_lines(text: str) -> list[str]:
    return text.splitlines()


def _find_header(lines: list[str], key: str) -> tuple[int, str]:
    """Ritorna (indice riga intestazione, separatore)."""
    for i, line in enumerate(lines[:20]):
        if key in norm(line):
            counts = {sep: line.count(sep) for sep in (";", "|", ",", "\t")}
            sep = max(counts, key=counts.get)
            if counts[sep] == 0:
                continue
            return i, sep
    raise ValueError(f"intestazione con '{key}' non trovata nelle prime righe")


def _col(header: list[str], aliases: Iterable[str], required: bool = True):
    normed = [norm(h) for h in header]
    for alias in aliases:
        if alias in normed:
            return normed.index(alias)
    if required:
        raise ValueError(f"colonna {tuple(aliases)} non trovata in {header}")
    return None


def to_float(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip().replace(",", ".")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_date(value: str | None) -> datetime | None:
    """Data naive in ora italiana (gestita da chi chiama)."""
    if not value:
        return None
    value = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def haversine_km(lat1, lng1, lat2, lng2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def parse_stations_in_radius(raw: bytes, lat: float, lng: float, radius_km: float) -> dict:
    """Anagrafica -> {id: {name, brand, address, latitude, longitude}} entro il raggio."""
    lines = _split_lines(decode(raw))
    h_idx, sep = _find_header(lines, "idimpianto")
    header = lines[h_idx].split(sep)
    c_id, c_lat, c_lng = _col(header, _ID), _col(header, _LAT), _col(header, _LNG)
    c_brand = _col(header, _BRAND, False)
    c_name = _col(header, _NAME, False)
    c_addr = _col(header, _ADDR, False)
    c_city = _col(header, _CITY, False)
    c_prov = _col(header, _PROV, False)

    def get(parts, idx):
        return parts[idx].strip() if idx is not None and idx < len(parts) else ""

    out = {}
    for line in lines[h_idx + 1:]:
        if not line.strip():
            continue
        parts = line.split(sep)
        slat, slng = to_float(get(parts, c_lat)), to_float(get(parts, c_lng))
        if slat is None or slng is None:
            continue
        # bounding box veloce prima dell'haversine
        if abs(slat - lat) > radius_km / 100 or abs(slng - lng) > radius_km / 60:
            continue
        if haversine_km(lat, lng, slat, slng) > radius_km:
            continue
        city, prov = get(parts, c_city), get(parts, c_prov)
        address = get(parts, c_addr)
        if city:
            address = f"{address}, {city}" + (f" ({prov})" if prov else "")
        out[get(parts, c_id)] = {
            "name": get(parts, c_name),
            "brand": get(parts, c_brand),
            "address": address,
            "latitude": slat,
            "longitude": slng,
        }
    return out


def parse_prices(raw: bytes, station_ids: set, fuel_names: dict) -> dict:
    """Prezzi -> {fuel_key: {id: {price, insert_date(str ISO), is_self}}}.

    fuel_names: {fuel_key: nome normalizzato (es. "gasolio")}.
    Per ogni stazione si preferisce il prezzo self; altrimenti il servito.
    """
    lines = _split_lines(decode(raw))
    h_idx, sep = _find_header(lines, "idimpianto")
    header = lines[h_idx].split(sep)
    c_id, c_fuel = _col(header, _ID), _col(header, _FUEL)
    c_price, c_self, c_date = _col(header, _PRICE), _col(header, _SELF), _col(header, _DATE, False)
    wanted = {norm(v): k for k, v in fuel_names.items()}

    out: dict = {k: {} for k in fuel_names}
    for line in lines[h_idx + 1:]:
        parts = line.split(sep)
        if len(parts) <= max(c_id, c_fuel, c_price, c_self):
            continue
        sid = parts[c_id].strip()
        if sid not in station_ids:
            continue
        fuel_key = wanted.get(norm(parts[c_fuel]))
        if fuel_key is None:
            continue
        price = to_float(parts[c_price])
        if not price:
            continue
        is_self = parts[c_self].strip().lower() in ("1", "true", "t", "si", "sì", "s")
        dt = parse_date(parts[c_date]) if c_date is not None and c_date < len(parts) else None
        prev = out[fuel_key].get(sid)
        # il self vince sul servito
        if prev is None or (is_self and not prev["is_self"]):
            out[fuel_key][sid] = {
                "price": price,
                "insert_date": dt.isoformat() if dt else None,
                "is_self": is_self,
            }
    return out
