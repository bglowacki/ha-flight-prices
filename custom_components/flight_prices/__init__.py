"""The Flight Prices integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_VERSION
from .coordinator import FlightPricesConfigEntry, FlightPricesCoordinator
from .sources.google import GoogleSource
from .sources.ryanair import RyanairSource

PLATFORMS = [Platform.SENSOR]


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
