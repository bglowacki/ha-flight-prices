"""Google Flights, read from its search page: every airline, one one-way search per request.

fast-flights builds the search (the protobuf in the ``tfs`` parameter). The page is fetched
and read here: the library sends no consent cookies, so from the EU Google answers with its
consent page, and its parser skips the "best flights" Google lists apart and the flight
numbers. This is the only module that imports fast_flights, so it can be swapped easily.

Everything here blocks: run it in the executor.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
import json
import logging
from typing import Any

from fast_flights import FlightQuery, Passengers, create_query
from primp import Client
from selectolax.lexbor import LexborHTMLParser

from ..models import Hours, Leg
from . import SourceBlocked, SourceError

_LOGGER = logging.getLogger(__name__)

URL = "https://www.google.com/travel/flights"
# The answer to Google's consent page, as a browser in the EU would send it.
CONSENT_COOKIES = "CONSENT=YES+cb.20230810-00-p0.it+FX+874; SOCS=CAESHAgBEhJnd3NfMjAyMzA4MTAtMF9SQzIaAml0IAEaBgiA_LyaBg"
TIMEOUT = 30.0


@dataclass(frozen=True)
class GoogleFlight:
    """A one-way flight and its price for one adult."""

    leg: Leg
    price: float


class GoogleSource:
    """Searches one way at a time."""

    def __init__(self, currency: str, language: str) -> None:
        self._currency = currency
        self._language = language.split("-")[0].lower() or "en"
        self._client: Client | None = None

    def search(self, day: date, origin: str, destination: str, hours: Hours, direct_only: bool) -> list[GoogleFlight]:
        """Flights leaving within the hours, cheapest first."""
        query = create_query(
            flights=[
                FlightQuery(
                    date=day.isoformat(),
                    from_airport=origin,
                    to_airport=destination,
                    earliest_departure_hour=hours.start or None,
                    latest_departure_hour=hours.end - 1 if hours.end < 24 else None,
                )
            ],
            trip="one-way",
            passengers=Passengers(adults=1),
            language=self._language,
            currency=self._currency,
            max_stops=0 if direct_only else None,
        )
        flights = parse_page(self._fetch(query.params()))
        return sorted(
            (
                flight
                for flight in flights
                if flight.leg.departure.date() == day
                and hours.contains(flight.leg.departure)
                and (flight.leg.stops == 0 or not direct_only)
            ),
            key=lambda flight: flight.price,
        )

    def link(self, origin: str, destination: str, outbound: date, inbound: date) -> str:
        """The return search on Google Flights."""
        query = create_query(
            flights=[
                FlightQuery(date=outbound.isoformat(), from_airport=origin, to_airport=destination),
                FlightQuery(date=inbound.isoformat(), from_airport=destination, to_airport=origin),
            ],
            trip="round-trip",
            passengers=Passengers(adults=1),
            language=self._language,
            currency=self._currency,
        )
        return query.url()

    def close(self) -> None:
        self._client = None

    def _fetch(self, params: dict[str, str]) -> str:
        if self._client is None:
            self._client = Client(
                impersonate="chrome_145",
                impersonate_os="macos",
                referer=True,
                cookie_store=True,
                follow_redirects=False,
                timeout=TIMEOUT,
            )
        try:
            response = self._client.get(URL, params=params, headers={"cookie": CONSENT_COOKIES})
        except Exception as err:  # primp raises its own exception types
            raise SourceError(f"Google Flights did not answer: {err}") from err
        status = response.status_code
        if status in (301, 302, 303, 307):
            location = response.headers.get("location", "")
            if "consent." in location:
                raise SourceBlocked("Google Flights asked for cookie consent")
            if "/sorry/" in location:
                raise SourceBlocked("Google Flights asked to solve a captcha")
            raise SourceBlocked(f"Google Flights redirected to {location.split('?')[0]}")
        if status == 429:
            raise SourceBlocked("Google Flights answered HTTP 429, too many requests")
        if status != 200:
            raise SourceError(f"Google Flights answered HTTP {status}")
        return response.text


def parse_page(html: str) -> list[GoogleFlight]:
    """Flights in the data Google embeds in the page (the ``ds:1`` script)."""
    script = LexborHTMLParser(html).css_first(r"script.ds\:1")
    if script is None:
        # Not the page we know: stop rather than read 160 pages we cannot use.
        raise SourceBlocked("Google Flights sent a page without flight data")
    text = script.text()
    try:
        data_text = text.split("data:", 1)[1].rsplit(",", 1)[0]
    except IndexError as err:
        raise SourceBlocked("Google Flights changed its flight data") from err
    if data_text.endswith("errorHasStatus: true"):
        return []
    try:
        payload = json.loads(data_text)
    except ValueError as err:
        raise SourceBlocked("Google Flights changed its flight data") from err
    flights = []
    # Index 2 holds what Google calls the best flights, index 3 the others.
    for block in (_get(payload, 2, 0), _get(payload, 3, 0)):
        for item in block or ():
            try:
                flight = _flight(item)
            except (IndexError, KeyError, TypeError, ValueError) as err:
                _LOGGER.debug("Skipping a Google flight that could not be read: %s", err)
                continue
            if flight is not None:
                flights.append(flight)
    return flights


def _flight(item: list[Any]) -> GoogleFlight | None:
    info, prices = item[0], item[1]
    price = _get(prices, 0, 1)
    if not price:
        return None
    segments = info[2]
    first, last = segments[0], segments[-1]
    numbers = tuple(f"{seg[22][0]}{seg[22][1]}" for seg in segments if seg[22] and seg[22][1])
    airlines = info[1] or [seg[22][3] for seg in segments if seg[22]]
    return GoogleFlight(
        leg=Leg(
            origin=first[3],
            destination=last[6],
            departure=_moment(first[20], first[8]),
            arrival=_moment(last[21], last[10]),
            flight_numbers=numbers,
            airline=", ".join(dict.fromkeys(airlines)),
            stops=len(segments) - 1,
        ),
        price=float(price),
    )


def _moment(day: list[int], clock: list[int | None] | None) -> datetime:
    """Google drops zero parts of a time: [8] is 08:00 and [None, 31] is 00:31."""
    padded = [*(clock or []), None, None]
    return datetime.combine(date(*day), time(padded[0] or 0, padded[1] or 0))


def _get(data: Any, *path: int) -> Any:
    for index in path:
        if not isinstance(data, list) or len(data) <= index:
            return None
        data = data[index]
    return data
