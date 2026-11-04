"""Tests for the config flow."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from custom_components.flight_prices.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import OPTIONS, make_entry

FORM = {
    "name": " Weekend ",
    "origins": ["mxp", " BGY", "MXP"],
    "sources": ["ryanair"],
    "weeks": 8,
    "outbound_day": "4",
    "outbound_from": 19,
    "outbound_to": 24,
    "return_day": "6",
    "return_from": 14,
    "return_to": 24,
    "direct_only": True,
}


@pytest.fixture(autouse=True)
def no_setup():
    with patch("custom_components.flight_prices.async_setup_entry", return_value=True):
        yield


async def test_create_anywhere(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], FORM)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Weekend"
    assert result["data"] == {}
    assert result["options"] == {**OPTIONS, "weeks": 8}


@pytest.mark.parametrize(
    ("changes", "errors"),
    [
        ({"origins": []}, {"origins": "no_origin"}),
        ({"origins": ["MALPENSA"]}, {"origins": "invalid_code"}),
        ({"destinations": ["LIS", "12"]}, {"destinations": "invalid_code"}),
        ({"sources": []}, {"sources": "no_source"}),
        ({"exclude_countries": ["ITA"]}, {"exclude_countries": "invalid_country"}),
        ({"sources": ["google"]}, {"destinations": "google_needs_destinations"}),
        ({"outbound_from": 20, "outbound_to": 19}, {"outbound_to": "invalid_hours"}),
        ({"return_from": 14, "return_to": 14}, {"return_to": "invalid_hours"}),
    ],
)
async def test_errors(hass: HomeAssistant, changes: dict[str, Any], errors: dict[str, str]) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {**FORM, **changes})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors


async def test_google_with_destinations(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**FORM, "sources": ["google"], "destinations": ["lis", "LON"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"]["destinations"] == ["LIS", "LON"]


async def test_exclude_countries(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {**FORM, "exclude_countries": ["it"]})
    assert result["options"]["exclude_countries"] == ["IT"]


async def test_same_search_twice(hass: HomeAssistant) -> None:
    make_entry().add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], FORM)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options(hass: HomeAssistant) -> None:
    entry = make_entry()
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    form = {key: value for key, value in FORM.items() if key != "name"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**form, "destinations": ["PMO"], "ryanair_interval": 6, "google_interval": 24}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["destinations"] == ["PMO"]
    assert entry.options["ryanair_interval"] == 6
