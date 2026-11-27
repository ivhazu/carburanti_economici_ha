"""Test del parser CSV MIMIT (senza Home Assistant)."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "csv_source",
    Path(__file__).parent.parent / "custom_components" / "carburanti_economici" / "csv_source.py",
)
cs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cs)

ANAG = (
    "Estrazione del 2026-11-14\n"
    "idImpianto;Gestore;Bandiera;Tipo Impianto;Nome Impianto;Indirizzo;Comune;Provincia;Latitudine;Longitudine\n"
    "1;Rossi;ENI;Stradale;Eni Roma;VIA ROMA 1;BRESCIA;BS;45.50;10.27\n"
    "2;Bianchi;Q8;Stradale;Q8 Lontano;VIA X 2;MILANO;MI;45.46;9.19\n"
    "3;Verdi;IP;Stradale;IP Vicino;VIA Y 3;BRESCIA;BS;45,52;10,30\n"
).encode()
PREZ = (
    "Estrazione del 2026-11-14\n"
    "idImpianto;descCarburante;prezzo;isSelf;dtComu\n"
    "1;Benzina;1,799;1;13/11/2026 07:30:00\n"
    "1;Benzina;1,899;0;13/11/2026 07:30:00\n"
    "3;Benzina;1,759;0;14/11/2026 06:00:00\n"
    "3;Benzina WR 100;2,5;1;14/11/2026 06:00:00\n"
    "2;Benzina;1,5;1;14/11/2026 06:00:00\n"
).encode()


def test_radius_filter_and_decimal_comma():
    st = cs.parse_stations_in_radius(ANAG, 45.5, 10.28, 10)
    assert sorted(st) == ["1", "3"]
    assert st["3"]["address"] == "VIA Y 3, BRESCIA (BS)"


def test_pipe_separator():
    st = cs.parse_stations_in_radius(ANAG.decode().replace(";", "|").encode(), 45.5, 10.28, 10)
    assert sorted(st) == ["1", "3"]


def test_prices_self_preferred_and_exact_fuel_name():
    p = cs.parse_prices(PREZ, {"1", "3"}, {"benzina": "benzina"})
    assert p["benzina"]["1"]["price"] == 1.799  # self vince sul servito
    assert p["benzina"]["3"]["price"] == 1.759  # "Benzina WR 100" escluso
    assert "2" not in p["benzina"]


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).parent.parent / "custom_components" / "carburanti_economici" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_marker_helpers():
    mk = _load("marker")
    assert mk.brand_slug("Agip Eni") == "agip_eni"
    assert mk.brand_slug("Api-Ip") == "api_ip"
    assert mk.brand_abbr("Esso") == "ESSO"
    assert mk.brand_abbr("Tamoil") == "TAM"
    assert mk.brand_abbr(None) == "?"
    uri = mk.marker_data_uri(2, "Q8")
    assert uri.startswith("data:image/svg+xml;utf8,%3Csvg")
    assert "Q8" in mk.marker_svg(2, "Q8")
    assert mk.brand_color("Q8") == mk.brand_color("q8")
