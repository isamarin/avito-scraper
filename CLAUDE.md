# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
python -m pip install -r requirements.txt   # bottle, cheroot, curl_cffi, marshmallow, pytest
python run.py                                # API on http://localhost:8000 (PORT=9000 to change)
python main.py                               # call the API functions directly, writes output/*.json
python -m pytest -q                          # all tests (offline, no network)
python -m pytest avito/test_parsers.py -q -k seller   # one file / subset
docker compose up --build                    # same server in a container
```

Run everything from the repo root: top-level modules (`config`, `cache`, `scraper_errors`, `schema_fields`) are imported flat, and `avito/*.py` and the tests put the repo root on `sys.path` themselves.

Env vars: `PORT`, `AVITO_PROXY` (e.g. `http://user:pass@host:port`, a rotating Russian residential proxy for volume). Everything else is a constant in `config.py` (retries, backoff, max proof-of-work complexity) or `avito/cache_config.py` (per-endpoint TTLs).

## Architecture

A bottle + cheroot HTTP API (16 threads) that scrapes www.avito.ru over plain HTTP with `curl_cffi` Chrome TLS impersonation. No browser. A request goes through these layers:

1. **`routes.py`**: the `ENDPOINTS` table mounts each of the 7 GET endpoints at both `/path` and `/avito/path` (the `/avito` prefix matches the hosted RapidAPI paths). `call()` validates the query with a schema, runs the api function, and maps errors: `ValueError`/`BadRequest` → 400, `NotFound` → 404, `UpstreamError` (blocks, `ParseError`) and `JSONDecodeError` → 502, anything else → 500. Paginated endpoints return a `pagination` dict that `paginate()` flattens (on a copy: the result is the cached object) into `count/per_page/current_page/total_pages/next/previous`. Read the query with `request.query.getunicode` (`query_dict()`), because bottle's `.get()` garbles Cyrillic.
2. **`avito/schemas.py` + `schema_fields.py`**: marshmallow schemas. `BaseSchema` rejects unknown params. Convention: **one param per input**, never a separate `id`/`url` pair. `ad`, `seller`, `location` and `category` each accept an id, a slug/name, or an avito.ru link. `RefField` subclasses delegate to resolvers in **`avito/refs.py`**, which normalize the value to a dict like `{kind, id}` / `{slug}` / `{name}` and raise `ValueError` with a user-facing message.
3. **`avito/api.py`**: one public function per endpoint (`ads_search`, `ad_details`, `seller_details`, `seller_ads`, `seller_reviews`, `locations_search`, `categories_list`). Each is wrapped in `cache.cached_call(namespace, data, fn, ttl)`, an in-process dict cache keyed on the validated params. This layer also finishes the lookups that need the site: location slug/name → id, category slug → id (via the cached category tree).
4. **`avito/fetch.py`**: transport. Its module docstring documents every upstream surface and the site's firewall behavior; read it before changing any request. Key points:
   - Each worker thread has its own `curl_cffi` session (`threading.local`). The cookie jar holds the proof-of-work clearance.
   - A first request gets HTTP 439. `_clear_pow` solves the sha256 proof-of-work (`solve_pow`) and retries.
   - A 429 IP captcha is not solvable. It raises `AvitoBlocked`, `_retrying` drops the session, and the retry runs on a fresh connection/exit.
   - JSON routes need `x-requested-with: XMLHttpRequest`.
   - `check=` callbacks inside the retry loop tell "really not found" (`AvitoNotFound`, never retried) apart from "degraded render" (`AvitoUpstreamError`, retried).
5. **`avito/parsers.py`**: pure functions from raw HTML/JSON to clean dicts. Pages carry state in embedded JSON (`__staticRouterHydrationData`, `data-mfe-state` scripts). Parsers tolerate missing keys and raise `ParseError` only when a payload is not the page it claims to be.

`scraper_errors.py` holds the shared exception bases (`UpstreamError`, `Blocked`, `BadRequest`, `NotFound`). `fetch.py` subclasses them as `Avito*`.

### Non-obvious behaviors

- **Sellers**: a profile slug (`/brands/<slug>`) and the 32-hex profile key (`/user/<key>/profile`) are different identifiers. The catalog and reviews JSON APIs only take the key. A bare 32-hex value is ambiguous (`kind: "hash"`): api.py tries it as a key first, then as a brand slug. Given a key, `seller_ads`/`seller_reviews` skip the profile page, because it is the flakiest surface (often rendered without its state). Otherwise the profile parse is cached once (`avito.seller`) and shared by all three seller endpoints.
- **Search**: at most 30 pages × 50 results (page 31 returns HTTP 400, which becomes an empty page). A `locationId` is always sent; it defaults to all of Russia (`refs.ALL_RUSSIA_ID`). A root category with no query renders a "landing" with no ads, so `_search` retries it sorted newest-first.
- `main.py` calls the api functions directly, bypassing the schemas. Refs must be pre-resolved there (e.g. `resolve_seller("americanauto")`).
- Comments about upstream behavior carry the date it was observed (e.g. "verified 2026-10-24"). Keep doing this when documenting new site behavior.

## Tests

The tests are offline and use real captured responses in `avito/fixtures/*.gz`. The `fixture(name)` helper in `test_parsers.py` gunzips them and JSON-decodes `.json` ones. The `avito/parsers.py` docstring lists what each fixture is. Date-relative parsing is tested against a fixed `NOW` (the capture day). `test_schemas.py` covers validation through `load_query`. `test_routes.py` drives the WSGI app with `fetch` stubbed (cache + pagination, error → HTTP status). To support a new page shape, capture a real response, gzip it into `avito/fixtures/`, and add a parser test.

## Adding or changing an endpoint

Touch all of these together:
- a schema in `avito/schemas.py`
- an impl in `avito/api.py` wrapped in `cached_call` with a new namespace
- a TTL in `avito/cache_config.py`
- a row in `routes.ENDPOINTS` (set `paginated=True` if the impl returns a `pagination` block)
- the endpoint table in `README.md`
