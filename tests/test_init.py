"""Tests for the coordinator and the sensors."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.flight_prices.models import Hours, Leg
from custom_components.flight_prices.sources import SourceBlocked, SourceError
from custom_components.flight_prices.sources.google import GoogleFlight
from custom_components.flight_prices.sources.ryanair import URL as RYANAIR_URL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import NOW, make_entry, ryanair_payload


@pytest.fixture(autouse=True)
def frozen(freezer: FrozenDateTimeFactory) -> FrozenDateTimeFactory:
    freezer.move_to(NOW)
    return freezer


async def _setup(hass: HomeAssistant, **options: Any):
    entry = make_entry(**options)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_ryanair_anywhere(hass: HomeAssistant, aioclient_mock: Any) -> None:
    aioclient_mock.get(RYANAIR_URL, json=ryanair_payload())
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.LOADED
    # Two airports, two weeks.
    assert aioclient_mock.call_count == 4

    week = hass.states.get("sensor.weekend_week_1")
    assert week is not None
    assert float(week.state) == 131.98
    assert week.attributes["unit_of_measurement"] == "EUR"
    assert week.attributes["outbound_date"] == "2026-11-06"
    assert week.attributes["return_date"] == "2026-11-08"
    # Both airports answered with the same fixture: one trip per destination is kept.
    assert week.attributes["destinations_found"] == 3
    first = week.attributes["trips"][0]
    assert first["city"] == "Varsavia"
    assert first["outbound"]["departure"] == "2026-11-06T19:00"
    assert first["return"]["flights"] == "FR1904"

    # The fixture is for 6 to 8 November only.
    assert hass.states.get("sensor.weekend_week_2").state == "unknown"
    cheapest = hass.states.get("sensor.weekend_cheapest_trip")
    assert float(cheapest.state) == 131.98
    assert cheapest.attributes["city"] == "Varsavia"
    search = hass.states.get("sensor.weekend_ryanair_search")
    assert search.state == "2026-11-04T10:00:00+00:00"
    assert search.attributes["error"] is None


async def test_saved_results_survive_a_reload(hass: HomeAssistant, aioclient_mock: Any, frozen) -> None:
    aioclient_mock.get(RYANAIR_URL, json=ryanair_payload())
    entry = await _setup(hass)
    assert aioclient_mock.call_count == 4

    frozen.tick(timedelta(hours=1))
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    # Not due yet: the saved trips are shown, nothing is searched.
    assert aioclient_mock.call_count == 4
    assert float(hass.states.get("sensor.weekend_week_1").state) == 131.98

    # Due after three hours.
    frozen.tick(timedelta(hours=2, minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert aioclient_mock.call_count == 8


async def test_changed_search_searches_again(hass: HomeAssistant, aioclient_mock: Any) -> None:
    aioclient_mock.get(RYANAIR_URL, json=ryanair_payload())
    entry = await _setup(hass)
    hass.config_entries.async_update_entry(entry, options={**entry.options, "outbound_from": 18})
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 8


async def test_ryanair_failure_keeps_old_trips(hass: HomeAssistant, aioclient_mock: Any, frozen) -> None:
    aioclient_mock.get(RYANAIR_URL, json=ryanair_payload())
    await _setup(hass)
    aioclient_mock.clear_requests()
    aioclient_mock.get(RYANAIR_URL, status=500)
    frozen.tick(timedelta(hours=3, minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert float(hass.states.get("sensor.weekend_week_1").state) == 131.98
    search = hass.states.get("sensor.weekend_ryanair_search")
    assert search.state == "2026-11-04T10:00:00+00:00"
    assert "500" in search.attributes["error"]


async def test_setup_retries_when_nothing_answers(hass: HomeAssistant, aioclient_mock: Any) -> None:
    aioclient_mock.get(RYANAIR_URL, status=500)
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_fewer_weeks_remove_entities(hass: HomeAssistant, aioclient_mock: Any) -> None:
    aioclient_mock.get(RYANAIR_URL, json=ryanair_payload())
    entry = await _setup(hass)
    hass.config_entries.async_update_entry(entry, options={**entry.options, "weeks": 1})
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("sensor", "flight_prices", f"{entry.entry_id}_week_2") is None
    assert registry.async_get_entity_id("sensor", "flight_prices", f"{entry.entry_id}_week_1") is not None


def _flight(origin: str, destination: str, day: date, hour: int, price: float, number: str) -> GoogleFlight:
    departure = datetime(day.year, day.month, day.day, hour, 0)
    return GoogleFlight(
        Leg(
            origin=origin,
            destination=destination,
            departure=departure,
            arrival=departure + timedelta(hours=2),
            flight_numbers=(number,),
            airline="easyJet",
        ),
        price,
    )


def _fake_google(blocked_after: int | None = None, failing: set[int] | None = None):
    calls: list[tuple] = []

    def search(day: date, origin: str, destination: str, hours: Hours, direct_only: bool) -> list[GoogleFlight]:
        calls.append((day, origin, destination))
        if blocked_after is not None and len(calls) > blocked_after:
            raise SourceBlocked("Google Flights asked to solve a captcha")
        if failing and len(calls) in failing:
            raise SourceError("timeout")
        if day.weekday() == 4:
            return [_flight(origin, destination, day, 20, 50 if origin == "MXP" else 70, "U21")]
        return [_flight(origin, destination, day, 18, 60, "U22")]

    return calls, search


async def test_google_round(hass: HomeAssistant, aioclient_mock: Any) -> None:
    calls, search = _fake_google()
    with (
        patch("custom_components.flight_prices.sources.google.GoogleSource.search", side_effect=search),
        patch("custom_components.flight_prices.sources.google.GoogleSource.link", return_value="https://g"),
    ):
        await _setup(hass, sources=["google"], destinations=["LIS"])
        await hass.async_block_till_done(wait_background_tasks=True)
    # Two weeks, one destination, two airports, outbound and return.
    assert len(calls) == 8
    week = hass.states.get("sensor.weekend_week_1")
    assert float(week.state) == 110
    trip = week.attributes["trips"][0]
    assert (trip["origin"], trip["source"], trip["link"]) == ("MXP", "google", "https://g")
    assert float(hass.states.get("sensor.weekend_lis").state) == 110
    assert hass.states.get("sensor.weekend_google_flights_search").attributes["running"] is False
    assert aioclient_mock.call_count == 0


async def test_google_block_stops_the_round(hass: HomeAssistant) -> None:
    calls, search = _fake_google(blocked_after=2)
    with (
        patch("custom_components.flight_prices.sources.google.GoogleSource.search", side_effect=search),
        patch("custom_components.flight_prices.sources.google.GoogleSource.link", return_value="https://g"),
    ):
        await _setup(hass, sources=["google"], destinations=["LIS"])
        await hass.async_block_till_done(wait_background_tasks=True)
    assert len(calls) == 3
    # What came before the block is kept.
    assert float(hass.states.get("sensor.weekend_week_1").state) == 110
    search_state = hass.states.get("sensor.weekend_google_flights_search")
    assert search_state.state == "unknown"
    assert "captcha" in search_state.attributes["error"]


async def test_google_single_error_goes_on(hass: HomeAssistant) -> None:
    calls, search = _fake_google(failing={1})
    with (
        patch("custom_components.flight_prices.sources.google.GoogleSource.search", side_effect=search),
        patch("custom_components.flight_prices.sources.google.GoogleSource.link", return_value="https://g"),
    ):
        await _setup(hass, sources=["google"], destinations=["LIS"])
        await hass.async_block_till_done(wait_background_tasks=True)
    # The first outbound failed, so its return was not searched.
    assert len(calls) == 7
    week = hass.states.get("sensor.weekend_week_1")
    # Only BGY is left for the first week.
    assert float(week.state) == 130
    assert hass.states.get("sensor.weekend_google_flights_search").state == "2026-11-04T10:00:00+00:00"


async def test_google_takes_names_from_ryanair(hass: HomeAssistant, aioclient_mock: Any) -> None:
    aioclient_mock.get(RYANAIR_URL, json=ryanair_payload())
    _calls, search = _fake_google()
    with (
        patch("custom_components.flight_prices.sources.google.GoogleSource.search", side_effect=search),
        patch("custom_components.flight_prices.sources.google.GoogleSource.link", return_value="https://g"),
    ):
        await _setup(hass, sources=["ryanair", "google"], destinations=["PMO", "WWA"])
        await hass.async_block_till_done(wait_background_tasks=True)
    week = hass.states.get("sensor.weekend_week_1")
    # Google is cheaper to both: 50 + 60 from MXP.
    assert [(trip["destination"], trip["city"], trip["source"]) for trip in week.attributes["trips"]] == [
        ("PMO", "Palermo", "google"),
        ("WWA", "Varsavia", "google"),
    ]
    assert hass.states.get("sensor.weekend_pmo").attributes["city"] == "Palermo"
