"""Offline tests for the /avito/* request schemas.

    python -m pytest avito/test_schemas.py -q
"""
import os
import sys

import pytest
from marshmallow import ValidationError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from avito import schemas  # noqa: E402
from schema_fields import load_query  # noqa: E402


def errors(schema_cls, query):
    data, body = load_query(schema_cls, query)
    assert data is None, f"expected a 400, loaded {data}"
    return body["errors"]


# ---- ads/search -----------------------------------------------------------------------------

def test_search_defaults():
    loaded = schemas.AdsSearchSchema().load({"query": "  bmw  x5 "})
    assert loaded == {"query": "bmw x5", "location": None, "category": None, "price_min": None,
                      "price_max": None, "filters": None, "seller_type": None, "with_photos_only": None,
                      "delivery_only": None, "title_only": None, "radius": None, "sort": "relevance",
                      "page": 1}


def test_search_every_input_form():
    loaded = schemas.AdsSearchSchema().load({
        "query": "toyota", "location": "https://www.avito.ru/kazan/avtomobili", "category": "avtomobili",
        "price_min": "500000", "price_max": "1500000", "filters": "110007:331253,2687:-50000",
        "seller_type": "Private", "with_photos_only": "yes", "delivery_only": "0", "title_only": "true",
        "radius": "50", "sort": "PRICE_ASC", "page": "3"})
    assert loaded["location"] == {"id": 650400}
    assert loaded["category"] == {"slug": "avtomobili"}
    assert loaded["filters"] == [["params[110007]", "331253"], ["params[2687][to]", "50000"]]
    assert loaded["seller_type"] == "private" and loaded["sort"] == "price_asc"
    assert loaded["with_photos_only"] is True and loaded["delivery_only"] is False
    assert loaded["price_min"] == 500000 and loaded["radius"] == 50 and loaded["page"] == 3


def test_search_location_and_category_forms():
    s = schemas.AdsSearchSchema()
    assert s.load({"category": "9"})["category"] == {"id": 9}
    assert s.load({"category": "9", "location": "637640"})["location"] == {"id": 637640}
    assert s.load({"category": "9", "location": "Казань"})["location"] == {"name": "Казань"}
    assert s.load({"category": "9", "location": "all"})["location"] == {"id": 621540}


def test_search_needs_query_or_category():
    assert "query" in errors(schemas.AdsSearchSchema, {})
    assert "query" in errors(schemas.AdsSearchSchema, {"price_min": "10"})


@pytest.mark.parametrize("query,field", [
    ({"query": "x", "page": "31"}, "page"),
    ({"query": "x", "page": "0"}, "page"),
    ({"query": "x", "sort": "cheapest"}, "sort"),
    ({"query": "x", "seller_type": "dealer"}, "seller_type"),
    ({"query": "x", "price_min": "-1"}, "price_min"),
    ({"query": "x", "price_min": "500", "price_max": "100"}, "price_min"),
    ({"query": "x", "filters": "brand:bmw"}, "filters"),
    ({"query": "x", "radius": "0"}, "radius"),
    ({"query": "x", "radius": "900"}, "radius"),
    ({"query": "x", "location": "https://www.avito.ru/brands/x"}, "location"),
    ({"query": "x", "category": "Автомобили"}, "category"),
    ({"category": "9", "title_only": "true"}, "title_only"),
    ({"query": "x", "with_photos_only": "maybe"}, "with_photos_only"),
    ({"query": "x", "url": "https://www.avito.ru/moskva"}, "url"),     # no sibling url param
])
def test_search_rejects(query, field):
    assert field in errors(schemas.AdsSearchSchema, query)


def test_search_error_message_names_the_problem():
    body = load_query(schemas.AdsSearchSchema, {"query": "x", "filters": "110007"})[1]
    assert body["error"].startswith("Invalid parameters: filters:")
    assert "<attribute id>:<value>" in body["error"]


# ---- ads/details ----------------------------------------------------------------------------

def test_ad_schema_accepts_id_and_link():
    assert schemas.AdSchema().load({"ad": "7726049894"}) == {"ad": 7726049894}
    assert schemas.AdSchema().load(
        {"ad": "https://www.avito.ru/moskva/avtomobili/bmw_x5_3.0_at_2025_16_000_km_7726049894?context=x"}
    ) == {"ad": 7726049894}


@pytest.mark.parametrize("query", [{}, {"ad": ""}, {"ad": "bmw"}, {"ad": "https://example.com/x_7726049894"},
                                   {"ad": "7726049894", "id": "7726049894"}])
def test_ad_schema_rejects(query):
    with pytest.raises(ValidationError):
        schemas.AdSchema().load(query)


def test_ad_schema_message():
    assert errors(schemas.AdSchema, {"ad": "bmw"})["ad"] == [
        "Must be a numeric Avito ad id (7726049894) or an avito.ru ad link."]


# ---- sellers -----------------------------------------------------------------------------------

def test_seller_schemas():
    assert schemas.SellerSchema().load({"seller": "americanauto"}) == {
        "seller": {"kind": "brand", "id": "americanauto"}}
    loaded = schemas.SellerAdsSchema().load({"seller": "https://www.avito.ru/brands/i13285073",
                                              "category": "9", "sort": "newest", "page": "2"})
    assert loaded == {"seller": {"kind": "brand", "id": "i13285073"}, "category": {"id": 9},
                      "sort": "newest", "page": 2}
    loaded = schemas.SellerReviewsSchema().load({"seller": "6f089f8d4dbdc5987c77eb440d7612fe"})
    assert loaded == {"seller": {"kind": "hash", "id": "6f089f8d4dbdc5987c77eb440d7612fe"},
                      "sort": "newest", "with_photos_only": None, "page": 1}


@pytest.mark.parametrize("schema,query,field", [
    (schemas.SellerSchema, {}, "seller"),
    (schemas.SellerSchema, {"seller": "Американ Авто"}, "seller"),
    (schemas.SellerAdsSchema, {"seller": "americanauto", "page": "201"}, "page"),
    (schemas.SellerAdsSchema, {"seller": "americanauto", "sort": "rating"}, "sort"),
    (schemas.SellerReviewsSchema, {"seller": "americanauto", "sort": "price_asc"}, "sort"),
    (schemas.SellerReviewsSchema, {"seller": "americanauto", "page": "401"}, "page"),
])
def test_seller_schemas_reject(schema, query, field):
    assert field in errors(schema, query)


# ---- locations / categories --------------------------------------------------------

def test_locations_schema():
    assert schemas.LocationsSearchSchema().load({"query": "Казань"}) == {"query": "Казань", "limit": 10}
    assert "query" in errors(schemas.LocationsSearchSchema, {})
    assert "limit" in errors(schemas.LocationsSearchSchema, {"query": "x", "limit": "31"})


def test_categories_schema_takes_no_params():
    assert schemas.CategoriesListSchema().load({}) == {}
    assert "x" in errors(schemas.CategoriesListSchema, {"x": "1"})
