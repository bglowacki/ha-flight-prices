"""Fixtures for the Flight Prices tests."""

from __future__ import annotations

from collections.abc import Generator
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.flight_prices.const import (
    CONF_DESTINATIONS,
    CONF_DIRECT_ONLY,
    CONF_EXCLUDE_COUNTRIES,
    CONF_GOOGLE_DESTINATIONS,
    CONF_GOOGLE_ORIGINS,
    CONF_ORIGINS,
    CONF_OUTBOUND_DAY,
    CONF_OUTBOUND_FROM,
    CONF_OUTBOUND_TO,
    CONF_RETURN_DAY,
    CONF_RETURN_FROM,
    CONF_RETURN_TO,
    CONF_SOURCES,
    CONF_WEEKS,
    DOMAIN,
)

FIXTURES = Path(__file__).parent / "fixtures"
# A Wednesday: the first week is Friday 6 to Sunday 8 November 2026, as in the fixture.
NOW = "2026-11-04 10:00:00+00:00"

OPTIONS: dict[str, Any] = {
    CONF_ORIGINS: ["MXP", "BGY"],
    CONF_DESTINATIONS: [],
    CONF_EXCLUDE_COUNTRIES: [],
    CONF_SOURCES: ["ryanair"],
    CONF_GOOGLE_ORIGINS: [],
    CONF_GOOGLE_DESTINATIONS: [],
    CONF_WEEKS: 2,
    CONF_OUTBOUND_DAY: 4,
    CONF_OUTBOUND_FROM: 19,
    CONF_OUTBOUND_TO: 24,
    CONF_RETURN_DAY: 6,
    CONF_RETURN_FROM: 14,
    CONF_RETURN_TO: 24,
    CONF_DIRECT_ONLY: True,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load the integration from custom_components."""


@pytest.fixture(autouse=True)
def no_delays() -> Generator[None]:
    """The pauses between requests are for the real services only."""
    with (
        patch("custom_components.flight_prices.coordinator.RYANAIR_DELAY", 0),
        patch("custom_components.flight_prices.coordinator.GOOGLE_DELAY", (0, 0)),
    ):
        yield


def ryanair_payload() -> dict[str, Any]:
    """A real answer from BGY for 6 to 8 November 2026: Warsaw Modlin, Palermo, Edinburgh."""
    return json.loads((FIXTURES / "ryanair_bgy.json").read_text(encoding="utf-8"))


def make_entry(**options: Any) -> MockConfigEntry:
    return MockConfigEntry(domain=DOMAIN, title="Weekend", data={}, options={**OPTIONS, **options})
