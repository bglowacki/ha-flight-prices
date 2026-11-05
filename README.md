# Flight Prices for Home Assistant

Cheapest return flights for the coming weeks, as Home Assistant sensors. Each search has its own departure airports, destinations (or anywhere), outbound and return weekday and departure hours: for example out on Friday evening after 19:00 from Milan Malpensa or Bergamo and back on Sunday afternoon, or out on Thursday morning and back on Monday. Add as many searches as you like; all of it can be changed later from **Configure**.

Prices come from two sources, both read without an API key:

- **Ryanair**, through the fare finder behind ryanair.com. One request per departure airport and week returns the cheapest return fare to every destination, so this is the source that can search **anywhere**. Ryanair group flights only.
- **Google Flights**, read from its search page with [fast-flights](https://github.com/AWeirdDev/flights) building the search: every airline, but only for a list of destinations, one one-way search per request. Outbound and return are searched separately and added up: exact for low-cost airlines, an upper bound for airlines that price return trips lower. The booking links open Google Flights with the same hours and stops: a return search when one airline flies both ways (it may show a lower return fare), two one-way searches when the trip pairs two airlines.

> Neither source is an official API. They can change or stop answering at any time, and reading Google Flights automatically is against Google's terms of service. The integration keeps the requests few and spread out (see below) and stops at the first sign of a block. Use it for personal use, at your own risk.

## What you get

One device per search, with these sensors (prices for one adult, return trip):

| Sensor | State | Attributes |
|---|---|---|
| Week 1 … Week N | Cheapest trip of that week | `outbound_date`, `return_date`, the search (`origins`, `outbound_hours` and `return_hours` as `[from, to]`), `destinations_found`, `trips`: up to 30 trips, cheapest first, one per destination and departure airport, with city, country, country code, departure airport, price, airline, source, outbound and return flights (times, flight numbers, stops) and a booking link (`link`; with two airlines on Google Flights the trip is two tickets, so `link` is the outbound search and `return_link` the return one) |
| Cheapest trip | Cheapest trip of all the weeks | `outbound_date`, `return_date`, `city`, `trip` |
| One per destination, with a list | Cheapest trip to it over the weeks | `city`, `outbound_date`, `weeks` (price per week), `trip` |
| Ryanair search, Google Flights search (diagnostic) | Last successful search | `last_attempt`, `error`, `trips`, `running` |

Each week keeps one trip per destination and departure airport, the cheapest across sources, so a dashboard can filter by airport. Every trip comes back to the airport it left from. The lists in the attributes are not recorded in the history.

## Dashboard card

The integration ships a card, **Flight Prices**, already in the card picker: nothing to install or add as a resource. It shows one search:

- a summary with the cheapest trip, how many destinations were found and when each source last searched (red when a source keeps failing);
- a filter by departure airport, remembered on each device;
- one block per week with its cheapest destinations, each destination only once on the page: in rounds from the cheapest, every week gets its first, then its second and so on, so each destination sits in its cheapest week when there is room and no week is left empty. A trip that is cheaper in another week says so;
- the whole list of a week on a tap on its title;
- a tap on a trip opens the booking page; trips that are two tickets have an outbound and a return button.

```yaml
type: custom:flight-prices-card
device_id: <the search>   # optional with only one search
title: Weekends           # optional, the search's name by default
per_week: 3               # destinations per week before "show the others"
unique: true              # false: every week shows its own cheapest destinations
```

It reads the sensors of the search, so it follows the options: change the weeks, airports or hours and the card follows. In a sections view it takes the whole width and lays the weeks out in columns.

## Requests

| Source | Requests per search | Default interval |
|---|---|---|
| Ryanair | airports × weeks (2 × 8 = 16), one second apart | 3 hours |
| Google Flights | weeks × Google destinations × Google departure airports × 2 (8 × 5 × 1 × 2 = 80), 20 to 30 seconds apart, about half an hour in all | 24 hours |

The Google search runs in the background. Its round stops at the first block (consent page, captcha, HTTP 429) or after 5 errors in a row, and is tried again at the next interval. A return is not searched when the outbound found nothing. Results are saved, so a restart of Home Assistant or a change of options shows them at once without searching again, unless the search itself changed.

## Installation

With HACS: add this repository as a custom repository (category Integration), install **Flight Prices** and restart Home Assistant. By hand: copy `custom_components/flight_prices` into your `config/custom_components` and restart.

Then add the integration in **Settings → Devices & services**. The options can be changed later from the integration's **Configure** button.

| Option | What it is | Default |
|---|---|---|
| Departure airports | IATA codes; every trip comes back to the airport it left from | none, required |
| Destinations | IATA codes of airports or cities (`LON` is every London airport) | empty: anywhere (Ryanair only) |
| Leave out countries | ISO codes, such as `IT` for flights within Italy; applied to what was found, so changing it needs no new search | none |
| Sources | Ryanair, Google Flights or both | Ryanair |
| Google Flights destinations | Searched only on Google Flights, so Ryanair can keep searching anywhere | empty: the destinations above |
| Google Flights departure airports | Only these of the departure airports are searched on Google Flights, for example the ones Ryanair does not cover well | empty: all of them |
| Weeks | How many weeks ahead, from the coming one (1 to 12) | 8 |
| Outbound day and departure hours | Any weekday; hours from 0 to 24, 24 being midnight | Friday, 19 to 24 |
| Return day and departure hours | Any weekday; a return day before the outbound day means the week after (Saturday to Monday) | Sunday, 14 to 24 |
| Direct flights only | Google Flights only: Ryanair always flies direct | yes |
| Ryanair / Google Flights search every | Hours between two searches | 3 / 24 |

## Development

```
pip install -r requirements_test.txt
pytest
ruff check . && ruff format --check .
```

See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## Roadmap

- An event when a price drops below the lowest seen so far, for a destination or a week
- More than one passenger

## Credits

Google Flights searches are built with [fast-flights](https://github.com/AWeirdDev/flights).

Built with the help of AI coding agents (Claude Code), under the author's direction.

## License

MIT. Ryanair and Google Flights are trademarks of their owners; this project is not affiliated with them.
