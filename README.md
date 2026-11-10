# shopify-demand-matcher

![tests](https://github.com/Erick-QAtest/shopify-demand-matcher/actions/workflows/tests.yml/badge.svg)

Read-only matcher between what customers ask for and what a Shopify store actually has in stock.

I run a sneaker store, Sportland MX. Customers ask about models and sizes on WhatsApp, and those questions get logged as demand events. This tool takes each event, finds the matching Shopify variant (product + size) and reports whether it is available, out of stock, or not resolvable with the data the event carries.

It never writes anywhere. It reads the events log and the Shopify Admin API, and produces a CSV and a JSON report.

## Statuses

| Status | Meaning |
|---|---|
| `MATCH_AVAILABLE` | Product and size resolved, stock > 0 |
| `MATCH_OUT_OF_STOCK` | Product and size resolved, stock = 0 |
| `NEEDS_PRODUCT_RESOLUTION` | Size is known, product is not |
| `NEEDS_SIZE_RESOLUTION` | SKU is known, but there is no usable size |
| `NEEDS_PRODUCT_AND_SIZE_RESOLUTION` | Neither product nor size can be identified |
| `AMBIGUOUS_MATCH` | More than one variant fits |
| `SIZE_CONFLICT` | The SKU exists, but the requested size contradicts it and there isn't exactly one sibling variant in that size |
| `NO_SHOPIFY_MATCH` | SKU and size are known, but nothing in Shopify matches |

Five of the eight statuses mean "not resolved yet". That is on purpose. A wrong "out of stock" looks like an answer; an unresolved status tells you which data to fix.

## Rules worth knowing

- **Shopify is the source of truth** for product ID, variant ID, SKU, size option, inventory per location and price.
- **Size priority:** explicit size in the event, then size inside `meta_json`, then the size suffix of a legacy SKU.
- **Legacy SKUs are parsed conservatively.** `2033-27` and `1878L-23.5` carry a size. `951-1` does not: the `1` is a sequence number, so any suffix outside 10–50 is ignored instead of being read as a size.
- **Sibling variants:** if the SKU points to size 26 and the customer asked for 27, the matcher looks for the size-27 variant of the same product. If there isn't exactly one, it returns `SIZE_CONFLICT` instead of guessing.
- **Retries** with backoff on HTTP 429, GraphQL `THROTTLED` and 5xx. Pages of 50 variants, up to 10 locations per variant.
- **Phone numbers are excluded** from reports by default (`INCLUDE_PHONE=false`).

## V1 scope

Done means:

1. read the events log;
2. filter demand signals;
3. load Shopify variants and stock;
4. resolve at least one real event;
5. tell apart available, out of stock and unresolvable;
6. produce an auditable CSV/JSON;
7. zero writes.

Out of scope for V1, on purpose:

- VPS / Postgres;
- tracking when an out-of-stock size comes back (0 → stock);
- persisting customer intents;
- consent management;
- WhatsApp messaging;
- linking a request to a later purchase;
- scheduling.

## Live runs

**2026-09-28, first run against the live store.** 3 demand events read, 3 results, all `NEEDS_PRODUCT_AND_SIZE_RESOLUTION`. The integration worked end to end; none of those events carried enough product and size information to match. Reporting that was the correct output.

**V1.1.** 3,159 active variants loaded. A request for SKU `2072-26` in size 27 resolved to the sibling variant `2072-27` with `HIGH` confidence. Inventory 0, so `MATCH_OUT_OF_STOCK`.

## Run it

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Tests (offline, fixtures only):

```bash
pytest -q
```

Offline demo with the fixture catalog:

```bash
cp .env.example .env
SMART_CSV_PATH=tests/fixtures/smart_events.csv \
python run_match.py --shopify-fixture tests/fixtures/shopify_variants.json
```

Live run: export the events log as CSV (or point `SMART_SOURCE=sheets` to the Google Sheet through a service account), fill `SHOPIFY_SHOP`, `SHOPIFY_CLIENT_ID` and `SHOPIFY_CLIENT_SECRET` in `.env`, then:

```bash
python validate_config.py
python run_match.py
```

Output:

```text
artifacts/demand_supply_matches.csv
artifacts/demand_supply_summary.json
```

Event type names (`PREGUNTA_TALLA_PRECIO`, etc.) and match reasons are in Spanish because the source log is.
