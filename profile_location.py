"""Validate extracted geography and map canonical fields before resume rendering."""
import os
import re
import threading
import time
import unicodedata
from functools import lru_cache

import pycountry
from geopy.exc import GeopyError
from geopy.geocoders import Nominatim

from location_utils import clean_location

_lock = threading.Lock()
_last_request = 0.0


def _key(value):
    value = unicodedata.normalize("NFKD", str(value or ""))
    return re.sub(r"[^a-z0-9]", "", value.encode("ascii", "ignore").decode().lower())


def _country(value):
    aliases = {"usa": "US", "unitedstatesofamerica": "US", "uk": "GB"}
    try:
        return pycountry.countries.lookup(aliases.get(_key(value), value))
    except LookupError:
        return None


def _state(value, country_code):
    if not value:
        return None
    for state in pycountry.subdivisions.get(country_code=country_code):
        if _key(value) in {_key(state.name), _key(state.code), _key(state.code.split("-", 1)[-1])}:
            return state
    return None


@lru_cache(maxsize=2048)
def _lookup(city, state, country_code):
    global _last_request
    # Serialize and space geocoding calls even when multiple jobs run concurrently.
    with _lock:
        time.sleep(max(0, 1.1 - (time.monotonic() - _last_request)))
        try:
            locator = Nominatim(
                user_agent="recruit-profile-location-validator/1.0",
                domain=os.getenv("GEOCODER_DOMAIN", "nominatim.openstreetmap.org"),
                timeout=15,
            )
            return locator.geocode(
                {"city": city, "state": state, "country": country_code},
                exactly_one=False, limit=5, addressdetails=True,
                country_codes=country_code.lower(), language="en",
            )
        finally:
            _last_request = time.monotonic()


def validate_profile_location(profile):
    """Return valid/invalid/unknown; never guess a city from a job location."""
    city, state, country = (clean_location(profile.get(k)) for k in ("city", "state", "country"))
    result = dict(status="unknown", source="geopy+pycountry", city=city, state=state, country=country)
    if not city or not country:
        return dict(result, reason="Extracted city and country are required")
    country_record = _country(country)
    if country_record is None:
        return dict(result, status="invalid", reason="Unknown country")
    state_record = _state(state, country_record.alpha_2)
    if state and state_record is None:
        return dict(result, status="invalid", reason="State/province does not match country")
    try:
        matches = _lookup(city, state_record.name if state_record else "", country_record.alpha_2)
    except GeopyError as exc:
        return dict(result, reason=f"Geocoding unavailable: {type(exc).__name__}")
    if not matches:
        return dict(result, reason="City lookup returned no match")
    accepted = {}
    for match in matches:
        address = match.raw.get("address", {})
        found_city = next((address[k] for k in ("city", "town", "village", "municipality", "hamlet") if address.get(k)), "")
        found_state = _state(address.get("state", ""), country_record.alpha_2)
        if _key(found_city) != _key(city) or address.get("country_code", "").upper() != country_record.alpha_2:
            continue
        if state_record and (not found_state or found_state.code != state_record.code):
            continue
        canonical_state = found_state.name if found_state else ""
        accepted[(found_city, canonical_state)] = dict(
            result, status="valid", reason="City, state and country matched",
            city=found_city, state=canonical_state, country=country_record.name,
            location=", ".join(v for v in (found_city, canonical_state, country_record.name) if v),
        )
    if len(accepted) == 1:
        return next(iter(accepted.values()))
    return dict(result, reason="City match is ambiguous or does not match supplied geography")
