# Flight Prices for Home Assistant

Cheapest return flights for the coming weeks, as Home Assistant sensors: for example out on Friday evening after 19:00 from Milan Malpensa or Bergamo, back on Sunday afternoon, to anywhere or to a list of destinations.

Prices come from two sources, both read without an API key:

- **Ryanair**, through the fare finder behind ryanair.com. One request per departure airport and week returns the cheapest return fare to every destination, so this is the source that can search **anywhere**. Ryanair group flights only.
- **Google Flights**, read from its search page with [fast-flights](https://github.com/AWeirdDev/flights) building the search: every airline, but only for a list of destinations, one one-way search per request. Outbound and return are searched separately and added up: exact for low-cost airlines, an upper bound for airlines that price return trips lower.

> Neither source is an official API. They can change or stop answering at any time, and reading Google Flights automatically is against Google's terms of service. The integration keeps the requests few and spread out (see below) and stops at the first sign of a block. Use it for personal use, at your own risk.

## What you get

One device per search, with these sensors (prices for one adult, return trip):

| Sensor | State | Attributes |
|---|---|---|
| Week 1 … Week N | Cheapest trip of that week | `outbound_date`, `return_date`, `destinations_found`, `trips`: the 5 cheapest destinations with city, country, departure airport, price, airline, source, outbound and return flights (times, flight numbers, stops) and a booking link |
| Cheapest trip | Cheapest trip of all the weeks | `outbound_date`, `return_date`, `city`, `trip` |
| One per destination, with a list | Cheapest trip to it over the weeks | `city`, `outbound_date`, `weeks` (price per week), `trip` |
| Ryanair search, Google Flights search (diagnostic) | Last successful search | `last_attempt`, `error`, `trips`, `running` |

Each week keeps at most one trip per destination, the cheapest across departure airports and sources. Every trip comes back to the airport it left from. The lists in the attributes are not recorded in the history.

## Requests

| Source | Requests per search | Default interval |
|---|---|---|
| Ryanair | airports × weeks (2 × 8 = 16), one second apart | 3 hours |
| Google Flights | weeks × destinations × airports × 2 (8 × 5 × 2 × 2 = 160), 20 to 30 seconds apart, about an hour in all | 24 hours |

The Google search runs in the background. Its round stops at the first block (consent page, captcha, HTTP 429) or after 5 errors in a row, and is tried again at the next interval. A return is not searched when the outbound found nothing. Results are saved, so a restart of Home Assistant or a change of options shows them at once without searching again, unless the search itself changed.

## Installation

With HACS: add this repository as a custom repository (category Integration), install **Flight Prices** and restart Home Assistant. By hand: copy `custom_components/flight_prices` into your `config/custom_components` and restart.

Then add the integration in **Settings → Devices & services**. The options can be changed later from the integration's **Configure** button.

| Option | Default |
|---|---|
| Departure airports | IATA codes, such as `MXP`, `BGY` |
| Destinations | IATA codes of airports or cities (`LON` is every London airport); empty to search anywhere (Ryanair only) |
| Sources | Ryanair |
| Weeks | 8 |
| Outbound day and departure hours | Friday, 19 to 24 |
| Return day and departure hours | Sunday, 14 to 24 |
| Direct flights only (Google Flights) | Yes |
| Ryanair / Google Flights search every | 3 / 24 hours |

## Development

```
pip install -r requirements_test.txt
pytest
ruff check . && ruff format --check .
```

## License

MIT. Ryanair and Google Flights are trademarks of their owners; this project is not affiliated with them.
