"""Constants for the Flight Prices integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "flight_prices"

CONF_ORIGINS: Final = "origins"
# Empty means anywhere: every destination the sources fly to.
CONF_DESTINATIONS: Final = "destinations"
CONF_SOURCES: Final = "sources"
CONF_WEEKS: Final = "weeks"
CONF_OUTBOUND_DAY: Final = "outbound_day"
CONF_OUTBOUND_FROM: Final = "outbound_from"
CONF_OUTBOUND_TO: Final = "outbound_to"
CONF_RETURN_DAY: Final = "return_day"
CONF_RETURN_FROM: Final = "return_from"
CONF_RETURN_TO: Final = "return_to"
CONF_DIRECT_ONLY: Final = "direct_only"
CONF_RYANAIR_INTERVAL: Final = "ryanair_interval"
CONF_GOOGLE_INTERVAL: Final = "google_interval"

SOURCE_RYANAIR: Final = "ryanair"
SOURCE_GOOGLE: Final = "google"
SOURCES: Final = (SOURCE_RYANAIR, SOURCE_GOOGLE)

DEFAULT_WEEKS: Final = 8
MAX_WEEKS: Final = 12
# Friday evening out, Sunday afternoon or evening back. Days follow date.weekday().
DEFAULT_OUTBOUND_DAY: Final = 4
DEFAULT_OUTBOUND_FROM: Final = 19
DEFAULT_OUTBOUND_TO: Final = 24
DEFAULT_RETURN_DAY: Final = 6
DEFAULT_RETURN_FROM: Final = 14
DEFAULT_RETURN_TO: Final = 24
DEFAULT_DIRECT_ONLY: Final = True
DEFAULT_RYANAIR_HOURS: Final = 3
DEFAULT_GOOGLE_HOURS: Final = 24

# How often the coordinator checks whether a source is due.
TICK: Final = timedelta(minutes=15)

# Ryanair answers in a fraction of a second; a short pause keeps the requests polite.
RYANAIR_DELAY: Final = 1.0
# Google Flights is read without an API: the requests are spread out, so a search of
# 160 pages takes about an hour, and a block stops it at once.
GOOGLE_DELAY: Final = (20.0, 30.0)

# Trips kept per week, at most one per destination.
TRIPS_PER_WEEK: Final = 10
# Trips shown in the attributes of a week sensor.
TRIPS_IN_ATTRIBUTES: Final = 5

STORAGE_VERSION: Final = 1
