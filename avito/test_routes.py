"""Offline tests for routes.py: the cache + pagination seam and the
error -> HTTP mapping, through the WSGI app with the fetch layer stubbed.

    python -m pytest avito/test_routes.py -q
"""
import json
import os
import sys
from wsgiref.util import setup_testing_defaults

import bottle
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cache  # noqa: E402
import routes  # noqa: E402,F401  (mounts the routes on bottle's default app)
from avito import fetch  # noqa: E402
from avito.test_parsers import fixture  # noqa: E402


@pytest.fixture(autouse=True)
def empty_cache():
    cache._store.clear()


def get(path, query):
    env = {"PATH_INFO": path, "QUERY_STRING": query, "REQUEST_METHOD": "GET"}
    setup_testing_defaults(env)
    status = []
    body = b"".join(bottle.default_app()(env, lambda line, *_: status.append(line)))
    return int(status[0].split()[0]), json.loads(body)


def test_cached_search_keeps_pagination(monkeypatch):
    monkeypatch.setattr(fetch, "fetch_search", lambda query, page: fixture("search_bmw_moscow.json"))
    first = get("/ads/search", "query=bmw&location=637640&page=3")
    second = get("/ads/search", "query=bmw&location=637640&page=3")   # served from the cache
    assert first == second
    assert first[1]["current_page"] == 3 and first[1]["next"].endswith("page=4")


def test_unreadable_page_state_is_502_not_400(monkeypatch):
    # \x22 is a valid JS escape but not a JSON one: a layout change, not bad input
    page = 'window.__staticRouterHydrationData = JSON.parse("{\\x22a\\x22:1}")'
    monkeypatch.setattr(fetch, "fetch_item", lambda ad: (page, ""))
    status, body = get("/ads/details", "ad=7726049894")
    assert status == 502 and "failed" in body["error"]
