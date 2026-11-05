"""The Flight Prices integration."""

from __future__ import annotations

import hashlib
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, STORAGE_VERSION
from .coordinator import FlightPricesConfigEntry, FlightPricesCoordinator
from .sources.google import GoogleSource
from .sources.ryanair import RyanairSource

PLATFORMS = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# The dashboard card, served by the integration and loaded on every dashboard.
CARD_FILE = Path(__file__).parent / "frontend" / "flight-prices-card.js"
CARD_URL = f"/{DOMAIN}/flight-prices-card.js"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the card: it shows up in the card picker with nothing to add by hand."""
    content = await hass.async_add_executor_job(CARD_FILE.read_bytes)
    await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, str(CARD_FILE), cache_headers=True)])
    # A new file gets a new address, so browsers do not keep the old one in cache.
    add_extra_js_url(hass, f"{CARD_URL}?v={hashlib.sha256(content).hexdigest()[:8]}")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: FlightPricesConfigEntry) -> bool:
    """Set up a search from a config entry."""
    currency, language = hass.config.currency, hass.config.language
    coordinator = FlightPricesCoordinator(
        hass,
        entry,
        RyanairSource(async_get_clientsession(hass), currency, language),
        GoogleSource(currency, language),
    )
    await coordinator.async_load()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FlightPricesConfigEntry) -> bool:
    """Unload a config entry; a Google search still running is cancelled with it."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: FlightPricesConfigEntry) -> None:
    """Delete what the search had found."""
    await Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}").async_remove()
