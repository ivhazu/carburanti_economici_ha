"""Neutral map-marker badge for a fuel station (SVG data URI).

The Home Assistant map card shows an entity's ``entity_picture`` as the pin.
Without one it shows the initials of the entity name (e.g. "1DB").
This module builds a small generic badge: a coloured circle with the brand
abbreviation and the ranking number. No brand logos are bundled.
"""
from __future__ import annotations

import hashlib
import re
from urllib.parse import quote


def brand_slug(brand: str | None) -> str:
    """'Agip Eni' -> 'agip_eni' (used for custom logo file names)."""
    return re.sub(r"[^a-z0-9]+", "_", (brand or "").lower()).strip("_")


def brand_abbr(brand: str | None) -> str:
    tokens = re.findall(r"[A-Za-z0-9]+", brand or "")
    if not tokens:
        return "?"
    word = tokens[0]
    return (word if len(word) <= 4 else word[:3]).upper()


def brand_color(brand: str | None) -> str:
    """Stable colour derived from the brand name (not the brand's own colours)."""
    digest = hashlib.md5(brand_slug(brand).encode()).digest()
    hue = int.from_bytes(digest[:2], "big") % 360
    return f"hsl({hue},55%,38%)"


def marker_svg(rank: int, brand: str | None) -> str:
    abbr = brand_abbr(brand)
    color = brand_color(brand)
    size = {1: 32, 2: 32, 3: 26}.get(len(abbr), 20)
    return (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 96 96'>"
        f"<circle cx='48' cy='48' r='45' fill='{color}' stroke='white' stroke-width='4'/>"
        f"<text x='46' y='68' font-family='Arial,Helvetica,sans-serif' "
        f"font-weight='700' font-size='{size}' fill='white' text-anchor='middle'>{abbr}</text>"
        f"<circle cx='72' cy='24' r='13' fill='white' stroke='{color}' stroke-width='3'/>"
        f"<text x='72' y='31' font-family='Arial,Helvetica,sans-serif' font-weight='700' "
        f"font-size='20' fill='{color}' text-anchor='middle'>{int(rank)}</text>"
        "</svg>"
    )


def marker_data_uri(rank: int, brand: str | None) -> str:
    return "data:image/svg+xml;utf8," + quote(marker_svg(rank, brand), safe="")
