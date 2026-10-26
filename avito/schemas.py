"""Marshmallow request schemas for every /avito/* route.

ONE param per input (tripadvisor QueryOrIdField convention, never a sibling
`url`/`id` pair):

    ad        a numeric ad id (7726049894) OR any avito.ru ad link
    seller    a profile slug (americanauto, i13285073), the 32-character
              profile key, OR an avito.ru profile link (/brands/<slug>,
              /user/<key>/profile)
    location  a location id (637640), a place name (Казань), a location
              slug (kazan) OR an avito.ru location / listing link
    category  a category id (9), a category slug (avtomobili) OR an
              avito.ru listing link

The resolvers live in avito/refs.py; names and slugs that need the site
finish resolving in avito/api.py.
"""
from marshmallow import ValidationError, fields, validate, validates_schema

from schema_fields import (BaseSchema, ChoiceField, Flag, LimitField, PageField, PositiveInt,
                           QueryField, RefField, StrippedString)
from avito import refs

# The site serves at most 1,500 results per search: 30 pages of 50.
MAX_SEARCH_PAGE = 30
# A profile lists every active ad; the biggest dealers run a few thousand.
MAX_SELLER_ADS_PAGE = 200
# 25 reviews a page; the busiest sellers carry several thousand.
MAX_REVIEWS_PAGE = 400


def _max_length(n):
    """Length(max=n) that tolerates the None an optional StrippedString
    yields for an empty value (`?query=&category=9`): the plain validator
    would len(None) into a TypeError that escapes load_query as a 500."""
    return lambda value: value is None or bool(validate.Length(max=n)(value))


class AdRefField(RefField):
    resolver = staticmethod(refs.resolve_ad)


class SellerRefField(RefField):
    resolver = staticmethod(refs.resolve_seller)


class LocationRefField(RefField):
    resolver = staticmethod(refs.resolve_location)

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("load_default", None)
        super().__init__(**kwargs)


class CategoryRefField(RefField):
    resolver = staticmethod(refs.resolve_category)

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("load_default", None)
        super().__init__(**kwargs)


class FiltersField(StrippedString):
    """'110007:331253,2687:-50000' -> [[query key, value], ...] for the
    site's params[...] (refs.parse_filters)."""

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("load_default", None)
        super().__init__(**kwargs)

    def _deserialize(self, value, attr, data, **kwargs):
        value = super()._deserialize(value, attr, data, **kwargs)
        if value is None:
            return None
        try:
            pairs = refs.parse_filters(value)
        except ValueError as e:
            raise ValidationError(str(e))
        return [list(p) for p in pairs] or None


class RubleField(fields.Integer):
    """A price bound in rubles (whole number, 0 or more). Optional."""

    def __init__(self, **kwargs):
        kwargs.setdefault("load_default", None)
        kwargs.setdefault("validate", validate.Range(min=0, max=10_000_000_000))
        super().__init__(strict=False, **kwargs)


class AdsSearchSchema(BaseSchema):
    query = StrippedString(load_default=None, validate=_max_length(200), metadata={
        "description": "words to search for (required unless category is given)"})
    location = LocationRefField(metadata={
        "description": "where to search: a location id (637640), a place name (Казань), a slug (kazan) "
                       "or an avito.ru location link; all of Russia when omitted"})
    category = CategoryRefField(metadata={
        "description": "a category id (9), slug (avtomobili) or an avito.ru listing link; "
                       "see /avito/categories/list"})
    price_min = RubleField(metadata={"description": "lowest price in rubles"})
    price_max = RubleField(metadata={"description": "highest price in rubles"})
    filters = FiltersField(metadata={
        "description": "attribute filters as <attribute id>:<value id> pairs, comma-separated; "
                       "several values with | (110008:331255|331257), numeric ranges as min-max "
                       "(2687:-50000, 164669:2018-2022). The ids come back in a search's `filters`"})
    seller_type = ChoiceField(list(refs.SELLER_TYPES), metadata={
        "description": "only ads from private sellers or from companies"})
    with_photos_only = Flag(metadata={"description": "only ads with photos"})
    delivery_only = Flag(metadata={"description": "only ads that ship with Avito Delivery"})
    title_only = Flag(metadata={"description": "match the query in ad titles only"})
    radius = PositiveInt(max_value=500, metadata={
        "description": "also include ads within this many km of the location"})
    sort = ChoiceField(list(refs.SORTS), load_default="relevance", metadata={
        "description": "relevance (default), price_asc, price_desc or newest"})
    page = PageField(max_page=MAX_SEARCH_PAGE, metadata={
        "description": "results page, 50 ads each; the site serves at most 30 pages"})

    @validates_schema
    def _check(self, data, **kwargs):
        if not data.get("query") and not data.get("category"):
            raise ValidationError("Give a query, a category, or both.", "query")
        lo, hi = data.get("price_min"), data.get("price_max")
        if lo is not None and hi is not None and lo > hi:
            raise ValidationError("price_min must not exceed price_max.", "price_min")
        if data.get("title_only") and not data.get("query"):
            raise ValidationError("title_only needs a query.", "title_only")


class AdSchema(BaseSchema):
    ad = AdRefField(metadata={"description": "a numeric Avito ad id (7726049894) or an avito.ru ad link"})


class LocationsSearchSchema(BaseSchema):
    query = QueryField(max_length=100, metadata={"description": "a place name, in Russian (Казань, Тверь)"})
    limit = LimitField(default=10, max_size=30, metadata={"description": "how many locations (1-30)"})


class CategoriesListSchema(BaseSchema):
    """No params: the whole category navigation tree."""


class SellerSchema(BaseSchema):
    seller = SellerRefField(metadata={
        "description": "a profile slug (americanauto, i13285073), the 32-character profile key, "
                       "or an avito.ru profile link"})


class SellerAdsSchema(SellerSchema):
    category = CategoryRefField(metadata={
        "description": "only this category's ads (id, slug or avito.ru listing link)"})
    sort = ChoiceField(list(refs.SORTS), load_default="relevance", metadata={
        "description": "relevance (default), price_asc, price_desc or newest"})
    page = PageField(max_page=MAX_SELLER_ADS_PAGE, metadata={"description": "results page, 50 ads each"})


class SellerReviewsSchema(SellerSchema):
    sort = ChoiceField(list(refs.REVIEW_SORTS), load_default="newest", metadata={
        "description": "newest (default), oldest, positive or negative"})
    with_photos_only = Flag(metadata={"description": "only reviews with photos"})
    page = PageField(max_page=MAX_REVIEWS_PAGE, metadata={"description": "results page, 25 reviews each"})
