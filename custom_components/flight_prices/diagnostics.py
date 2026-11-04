"""Diagnostics for the Flight Prices integration."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import FlightPricesConfigEntry


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: FlightPricesConfigEntry) -> dict[str, Any]:
    """The search, the state of each source and how many trips each week has. Nothing personal is stored."""
    coordinator = entry.runtime_data
    data = coordinator.data
    return {
        "options": dict(entry.options),
        "google_running": coordinator.google_running,
        "sources": {
            name: {
                "last_attempt": state.last_attempt.isoformat() if state.last_attempt else None,
                "last_success": state.last_success.isoformat() if state.last_success else None,
                "error": state.error,
                "trips": len(state.trips),
            }
            for name, state in data.sources.items()
        },
        "weeks": [
            {
                "outbound": result.week.outbound.isoformat(),
                "inbound": result.week.inbound.isoformat(),
                "trips": len(result.trips),
                "cheapest": result.trips[0].price if result.trips else None,
            }
            for result in data.weeks
        ],
    }
