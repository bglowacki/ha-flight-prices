"""Sensors for the Flight Prices integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SOURCE_GOOGLE, TRIPS_IN_ATTRIBUTES
from .coordinator import FlightPricesConfigEntry, FlightPricesCoordinator
from .models import Trip, WeekResult

# Every entity reads the coordinator's data, nothing is fetched per entity.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: FlightPricesConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    params = coordinator.params
    entities: list[FlightPricesSensor] = [CheapestSensor(coordinator)]
    entities += [WeekSensor(coordinator, number) for number in range(1, params.weeks + 1)]
    entities += [DestinationSensor(coordinator, code) for code in params.destinations]
    entities += [SearchSensor(coordinator, source) for source in coordinator.active_sources]
    # Weeks, destinations or sources taken out of the search leave no stale entities behind.
    registry = er.async_get(hass)
    wanted = {entity.unique_id for entity in entities}
    for registered in er.async_entries_for_config_entry(registry, entry.entry_id):
        if registered.domain == "sensor" and registered.unique_id not in wanted:
            registry.async_remove(registered.entity_id)
    async_add_entities(entities)


class FlightPricesSensor(CoordinatorEntity[FlightPricesCoordinator], SensorEntity):
    """A sensor of one search."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FlightPricesCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            entry_type=DeviceEntryType.SERVICE,
        )


class PriceSensor(FlightPricesSensor):
    """A price for one adult, return."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator: FlightPricesCoordinator, key: str) -> None:
        super().__init__(coordinator, key)
        self._attr_native_unit_of_measurement = coordinator.hass.config.currency


def _week_dates(result: WeekResult) -> dict[str, Any]:
    return {"outbound_date": result.week.outbound.isoformat(), "return_date": result.week.inbound.isoformat()}


class WeekSensor(PriceSensor):
    """The cheapest trips of the n-th week from now."""

    _attr_translation_key = "week"
    _unrecorded_attributes = frozenset({"trips"})

    def __init__(self, coordinator: FlightPricesCoordinator, number: int) -> None:
        super().__init__(coordinator, f"week_{number}")
        self._index = number - 1
        self._attr_translation_placeholders = {"number": str(number)}

    @property
    def _result(self) -> WeekResult | None:
        weeks = self.coordinator.data.weeks
        return weeks[self._index] if self._index < len(weeks) else None

    @property
    def native_value(self) -> float | None:
        result = self._result
        return result.trips[0].price if result and result.trips else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if (result := self._result) is None:
            return None
        return {
            **_week_dates(result),
            "destinations_found": len(result.trips),
            "trips": [trip.as_attributes() for trip in result.trips[:TRIPS_IN_ATTRIBUTES]],
        }


class CheapestSensor(PriceSensor):
    """The cheapest trip of all the weeks."""

    _attr_translation_key = "cheapest"
    _unrecorded_attributes = frozenset({"trip"})

    def __init__(self, coordinator: FlightPricesCoordinator) -> None:
        super().__init__(coordinator, "cheapest")

    @property
    def _best(self) -> tuple[WeekResult, Trip] | None:
        candidates = [(result, result.trips[0]) for result in self.coordinator.data.weeks if result.trips]
        return min(candidates, key=lambda pair: pair[1].price, default=None)

    @property
    def native_value(self) -> float | None:
        return best[1].price if (best := self._best) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if (best := self._best) is None:
            return None
        result, trip = best
        return {**_week_dates(result), "city": trip.city or trip.destination, "trip": trip.as_attributes()}


class DestinationSensor(PriceSensor):
    """The cheapest trip to one destination of the list, over all the weeks."""

    _attr_translation_key = "destination"
    _unrecorded_attributes = frozenset({"weeks", "trip"})

    def __init__(self, coordinator: FlightPricesCoordinator, code: str) -> None:
        super().__init__(coordinator, f"destination_{code.lower()}")
        self._code = code
        self._attr_translation_placeholders = {"destination": code}

    def _trips(self) -> list[tuple[WeekResult, Trip]]:
        return [
            (result, trip)
            for result in self.coordinator.data.weeks
            for trip in result.trips
            if trip.destination == self._code
        ]

    @property
    def native_value(self) -> float | None:
        prices = [trip.price for _, trip in self._trips()]
        return min(prices) if prices else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        trips = self._trips()
        best = min(trips, key=lambda pair: pair[1].price, default=None)
        return {
            "city": best[1].city if best else None,
            "outbound_date": best[0].week.outbound.isoformat() if best else None,
            "weeks": [
                {**_week_dates(result), "price": trip.price, "airline": trip.airline, "source": trip.source}
                for result, trip in trips
            ],
            "trip": best[1].as_attributes() if best else None,
        }


class SearchSensor(FlightPricesSensor):
    """When a source last searched successfully, and the error of the last attempt."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: FlightPricesCoordinator, source: str) -> None:
        super().__init__(coordinator, f"{source}_search")
        self._source = source
        self._attr_translation_key = f"{source}_search"

    @property
    def native_value(self) -> datetime | None:
        state = self.coordinator.data.sources.get(self._source)
        return state.last_success if state else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if (state := self.coordinator.data.sources.get(self._source)) is None:
            return None
        attributes: dict[str, Any] = {
            "last_attempt": state.last_attempt.isoformat() if state.last_attempt else None,
            "error": state.error,
            "trips": len(state.trips),
        }
        if self._source == SOURCE_GOOGLE:
            attributes["running"] = self.coordinator.google_running
        return attributes
