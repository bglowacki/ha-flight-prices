"""Config flow for the Flight Prices integration."""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlowWithReload
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from .const import (
    CONF_DESTINATIONS,
    CONF_DIRECT_ONLY,
    CONF_EXCLUDE_COUNTRIES,
    CONF_GOOGLE_DESTINATIONS,
    CONF_GOOGLE_INTERVAL,
    CONF_GOOGLE_ORIGINS,
    CONF_ORIGINS,
    CONF_OUTBOUND_DAY,
    CONF_OUTBOUND_FROM,
    CONF_OUTBOUND_TO,
    CONF_RETURN_DAY,
    CONF_RETURN_FROM,
    CONF_RETURN_TO,
    CONF_RYANAIR_INTERVAL,
    CONF_SOURCES,
    CONF_WEEKS,
    DEFAULT_DIRECT_ONLY,
    DEFAULT_GOOGLE_HOURS,
    DEFAULT_OUTBOUND_DAY,
    DEFAULT_OUTBOUND_FROM,
    DEFAULT_OUTBOUND_TO,
    DEFAULT_RETURN_DAY,
    DEFAULT_RETURN_FROM,
    DEFAULT_RETURN_TO,
    DEFAULT_RYANAIR_HOURS,
    DEFAULT_WEEKS,
    DOMAIN,
    GOOGLE_MAX_REQUESTS_PER_DAY,
    GOOGLE_MIN_HOURS,
    GUIDE_URL,
    MAX_WEEKS,
    SOURCE_GOOGLE,
    SOURCE_RYANAIR,
    SOURCES,
)
from .coordinator import FlightPricesConfigEntry

AIRPORT_RE = re.compile(r"^[A-Z]{3}$")
COUNTRY_RE = re.compile(r"^[A-Z]{2}$")

CODES = TextSelector(TextSelectorConfig(multiple=True))
DAY = SelectSelector(
    SelectSelectorConfig(
        options=[str(day) for day in range(7)], translation_key="weekday", mode=SelectSelectorMode.DROPDOWN
    )
)


def _number(low: int, high: int, unit: str | None = None) -> NumberSelector:
    config = NumberSelectorConfig(min=low, max=high, step=1, mode=NumberSelectorMode.BOX)
    if unit:
        config["unit_of_measurement"] = unit
    return NumberSelector(config)


SEARCH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ORIGINS): CODES,
        vol.Optional(CONF_DESTINATIONS): CODES,
        vol.Optional(CONF_EXCLUDE_COUNTRIES): CODES,
        vol.Required(CONF_SOURCES, default=[SOURCE_RYANAIR]): SelectSelector(
            SelectSelectorConfig(
                options=list(SOURCES), multiple=True, translation_key="sources", mode=SelectSelectorMode.LIST
            )
        ),
        vol.Optional(CONF_GOOGLE_ORIGINS): CODES,
        vol.Optional(CONF_GOOGLE_DESTINATIONS): CODES,
        vol.Required(CONF_WEEKS, default=DEFAULT_WEEKS): _number(1, MAX_WEEKS),
        vol.Required(CONF_OUTBOUND_DAY, default=str(DEFAULT_OUTBOUND_DAY)): DAY,
        vol.Required(CONF_OUTBOUND_FROM, default=DEFAULT_OUTBOUND_FROM): _number(0, 23, "h"),
        vol.Required(CONF_OUTBOUND_TO, default=DEFAULT_OUTBOUND_TO): _number(1, 24, "h"),
        vol.Required(CONF_RETURN_DAY, default=str(DEFAULT_RETURN_DAY)): DAY,
        vol.Required(CONF_RETURN_FROM, default=DEFAULT_RETURN_FROM): _number(0, 23, "h"),
        vol.Required(CONF_RETURN_TO, default=DEFAULT_RETURN_TO): _number(1, 24, "h"),
        vol.Required(CONF_DIRECT_ONLY, default=DEFAULT_DIRECT_ONLY): BooleanSelector(),
    }
)
USER_SCHEMA = vol.Schema({vol.Required(CONF_NAME): TextSelector()}).extend(SEARCH_SCHEMA.schema)
OPTIONS_SCHEMA = SEARCH_SCHEMA.extend(
    {
        vol.Required(CONF_RYANAIR_INTERVAL, default=DEFAULT_RYANAIR_HOURS): _number(1, 24, "h"),
        vol.Required(CONF_GOOGLE_INTERVAL, default=DEFAULT_GOOGLE_HOURS): _number(GOOGLE_MIN_HOURS, 168, "h"),
    }
)


def _codes(values: Any) -> list[str]:
    """MXP, " bgy " and duplicates become ["MXP", "BGY"]."""
    if isinstance(values, str):
        values = re.split(r"[\s,;]+", values)
    return list(dict.fromkeys(code.strip().upper() for code in values or () if code.strip()))


def google_requests_per_day(options: Mapping[str, Any]) -> int:
    """The most requests Google Flights makes in a day: weeks x destinations x airports x 2, per round."""
    if SOURCE_GOOGLE not in options.get(CONF_SOURCES, ()):
        return 0
    destinations = options.get(CONF_GOOGLE_DESTINATIONS) or options.get(CONF_DESTINATIONS) or ()
    origins = options.get(CONF_GOOGLE_ORIGINS) or options.get(CONF_ORIGINS) or ()
    per_round = int(options.get(CONF_WEEKS, DEFAULT_WEEKS)) * len(destinations) * len(origins) * 2
    hours = max(int(options.get(CONF_GOOGLE_INTERVAL, DEFAULT_GOOGLE_HOURS)), GOOGLE_MIN_HOURS)
    return -(-per_round * 24 // hours)


def placeholders(options: Mapping[str, Any]) -> dict[str, str]:
    return {
        "guide_url": GUIDE_URL,
        "count": str(google_requests_per_day(options)),
        "limit": str(GOOGLE_MAX_REQUESTS_PER_DAY),
    }


def validate(user_input: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    """The options to store, and the errors to show."""
    errors: dict[str, str] = {}
    origins = _codes(user_input.get(CONF_ORIGINS))
    destinations = _codes(user_input.get(CONF_DESTINATIONS))
    countries = _codes(user_input.get(CONF_EXCLUDE_COUNTRIES))
    google_origins = _codes(user_input.get(CONF_GOOGLE_ORIGINS))
    google_destinations = _codes(user_input.get(CONF_GOOGLE_DESTINATIONS))
    sources = [source for source in SOURCES if source in user_input.get(CONF_SOURCES, ())]
    if not origins:
        errors[CONF_ORIGINS] = "no_origin"
    elif not all(AIRPORT_RE.match(code) for code in origins):
        errors[CONF_ORIGINS] = "invalid_code"
    if not all(AIRPORT_RE.match(code) for code in destinations):
        errors[CONF_DESTINATIONS] = "invalid_code"
    if not all(AIRPORT_RE.match(code) for code in google_origins):
        errors[CONF_GOOGLE_ORIGINS] = "invalid_code"
    if not all(AIRPORT_RE.match(code) for code in google_destinations):
        errors[CONF_GOOGLE_DESTINATIONS] = "invalid_code"
    if not all(COUNTRY_RE.match(code) for code in countries):
        errors[CONF_EXCLUDE_COUNTRIES] = "invalid_country"
    if not sources:
        errors[CONF_SOURCES] = "no_source"
    elif SOURCE_GOOGLE in sources and not (google_destinations or destinations):
        # Google Flights is searched route by route: it cannot look everywhere.
        errors[CONF_GOOGLE_DESTINATIONS] = "google_needs_destinations"
    options: dict[str, Any] = {
        CONF_ORIGINS: origins,
        CONF_DESTINATIONS: destinations,
        CONF_EXCLUDE_COUNTRIES: countries,
        CONF_SOURCES: sources,
        CONF_GOOGLE_ORIGINS: google_origins,
        CONF_GOOGLE_DESTINATIONS: google_destinations,
        CONF_WEEKS: int(user_input[CONF_WEEKS]),
        CONF_OUTBOUND_DAY: int(user_input[CONF_OUTBOUND_DAY]),
        CONF_OUTBOUND_FROM: int(user_input[CONF_OUTBOUND_FROM]),
        CONF_OUTBOUND_TO: int(user_input[CONF_OUTBOUND_TO]),
        CONF_RETURN_DAY: int(user_input[CONF_RETURN_DAY]),
        CONF_RETURN_FROM: int(user_input[CONF_RETURN_FROM]),
        CONF_RETURN_TO: int(user_input[CONF_RETURN_TO]),
        CONF_DIRECT_ONLY: bool(user_input[CONF_DIRECT_ONLY]),
    }
    if options[CONF_OUTBOUND_FROM] >= options[CONF_OUTBOUND_TO]:
        errors[CONF_OUTBOUND_TO] = "invalid_hours"
    if options[CONF_RETURN_FROM] >= options[CONF_RETURN_TO]:
        errors[CONF_RETURN_TO] = "invalid_hours"
    for key in (CONF_RYANAIR_INTERVAL, CONF_GOOGLE_INTERVAL):
        if key in user_input:
            options[key] = int(user_input[key])
    # The interval cannot go under GOOGLE_MIN_HOURS: its field does not accept it.
    if google_requests_per_day(options) > GOOGLE_MAX_REQUESTS_PER_DAY:
        # Many requests from one address get it a captcha from Google, for the whole home.
        errors.setdefault(CONF_GOOGLE_DESTINATIONS, "google_too_many")
    return options, errors


def _suggested(options: Mapping[str, Any]) -> dict[str, Any]:
    """Stored options as the form shows them: the days are strings in the selector."""
    values = dict(options)
    for key in (CONF_OUTBOUND_DAY, CONF_RETURN_DAY):
        if key in values:
            values[key] = str(values[key])
    return values


class FlightPricesConfigFlow(ConfigFlow, domain=DOMAIN):
    """One entry per search: from where, to where, on which days."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: FlightPricesConfigEntry) -> FlightPricesOptionsFlow:
        return FlightPricesOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        options: dict[str, Any] = {}
        if user_input is not None:
            options, errors = validate(user_input)
            if not errors:
                self._async_abort_entries_match(
                    {key: options[key] for key in (CONF_ORIGINS, CONF_DESTINATIONS, CONF_OUTBOUND_DAY, CONF_RETURN_DAY)}
                )
                return self.async_create_entry(title=user_input[CONF_NAME].strip(), data={}, options=options)
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, _suggested(user_input or {})),
            errors=errors,
            description_placeholders=placeholders(options),
        )


class FlightPricesOptionsFlow(OptionsFlowWithReload):
    """Change the search; the entry reloads and searches again what changed."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        options: dict[str, Any] = {}
        if user_input is not None:
            options, errors = validate(user_input)
            if not errors:
                return self.async_create_entry(data=options)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, _suggested(user_input or self.config_entry.options)
            ),
            errors=errors,
            description_placeholders=placeholders(options),
        )
