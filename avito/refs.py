"""Reference resolvers, the filter syntax and the site's sort / owner codes
for /avito/* (avito.ru, Russia's classifieds site).

ONE param per input (tripadvisor QueryOrIdField convention): every input
that names a record takes the bare id OR the avito.ru link for it. The
resolvers raise ValueError with a user-facing message (RefField turns it
into a 400). Resolvers that need the site (a location slug, a category
slug) only normalize here; avito/api.py finishes the lookup.

Identifier shapes (research 2026-10-23/24):
  * ad        numeric item id (7726049894). Every item URL ends in
              `_<id>` (/moskva/avtomobili/bmw_x5_..._7726049894) and the
              site also serves /<id> alone (it redirects to the canonical
              path), so the id is all a details call needs.
  * seller    a public profile is /brands/<slug> where the slug is a shop
              name ("americanauto"), "i" + the numeric user id
              ("i13285073") or a 32-hex hash for private sellers; the same
              profile also answers /user/<profile key>/profile, where the
              32-hex profile key is what the catalog and review APIs take
              (/web/1/profile/items?sellerId=<key>, /web/7/user/<key>/ratings).
              A bare 32-hex value is therefore ambiguous: api.py tries it as
              a profile key first, then as a brand slug.
  * location  numeric location id (637640 Moscow, 621540 all Russia), a
              place name ("Казань", resolved through the site's own
              location search), or a latin slug / avito.ru link ("kazan",
              https://www.avito.ru/kazan/...): the big cities and regions
              come from LOCATION_SLUGS below, any other slug is resolved
              from that location's own page (the JSON routes take ids only
              and their location search does not match latin slugs).
  * category  numeric category id (9 cars, 24 flats), a slug ("avtomobili")
              or an avito.ru listing link (the slug is its second path
              segment). Slugs resolve through the site's category tree.
"""
import re
from urllib.parse import unquote, urlparse

SITE = "https://www.avito.ru"
ALL_RUSSIA_ID = 621540
ALL_RUSSIA_SLUG = "all"
CURRENCY = "RUB"

# Search sort codes (the `s` param; the site's own select "Сортировать",
# values read from filtersV2 2026-10-24).
SORTS = {"relevance": "101", "price_asc": "1", "price_desc": "2", "newest": "104"}
# `user` param: the site's "Частные" / "Компании" owner filter.
SELLER_TYPES = {"private": "1", "company": "2"}
# /web/7/user/<key>/ratings `sortRating` (the profile page's own select).
REVIEW_SORTS = {"newest": "date_desc", "oldest": "date_asc",
                "positive": "score_desc", "negative": "score_asc"}

ITEM_ID_RE = re.compile(r"^[0-9]{5,12}$")
HEX32_RE = re.compile(r"^[0-9a-f]{32}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]{1,79}$")
_PATH_ITEM_RE = re.compile(r"_([0-9]{5,12})/?$")
_LATIN_SLUG_RE = re.compile(r"^[a-z][a-z0-9_\-]{1,79}$")

# Location slug -> id for the biggest cities and regions, so a link or slug
# for them never costs the 1.7 MB location page. Each id came from the
# site's own location search (/web/1/slocations, exact name) and was
# verified 2026-10-24 by the slug /web/1/js/items echoes back for it.
LOCATION_SLUGS = {
    "moskva": 637640,                  # Москва
    "sankt-peterburg": 653240,         # Санкт-Петербург
    "novosibirsk": 641780,             # Новосибирск
    "ekaterinburg": 654070,            # Екатеринбург
    "kazan": 650400,                   # Казань
    "nizhniy_novgorod": 640860,        # Нижний Новгород
    "chelyabinsk": 661420,             # Челябинск
    "samara": 653040,                  # Самара
    "omsk": 642320,                    # Омск
    "rostov-na-donu": 652000,          # Ростов-на-Дону
    "ufa": 646600,                     # Уфа
    "krasnoyarsk": 635320,             # Красноярск
    "voronezh": 625810,                # Воронеж
    "perm": 644200,                    # Пермь
    "volgograd": 624840,               # Волгоград
    "krasnodar": 633540,               # Краснодар
    "saratov": 653241,                 # Саратов
    "tyumen": 659020,                  # Тюмень
    "sochi": 634450,                   # Сочи
    "moskovskaya_oblast": 637680,      # Московская область
    "leningradskaya_oblast": 636370,   # Ленинградская область
    "krasnodarskiy_kray": 632660,      # Краснодарский край
}

# Path segments that are site sections, never a location slug.
_NON_LOCATION_SEGMENTS = {"brands", "user", "web", "catalog", "items", "profile", "not-found",
                          "regions", "business", "favorites", "evaluation", "paid-services"}


def _is_link(value):
    return value.startswith(("http://", "https://", "//", "www.avito.ru", "avito.ru", "m.avito.ru"))


def _parse_link(value):
    """An avito.ru URL -> its decoded path segments; ValueError for another host."""
    url = value
    if url.startswith("//"):
        url = "https:" + url
    elif not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not (host == "avito.ru" or host.endswith(".avito.ru")):
        raise ValueError("Must be an avito.ru link.")
    return [unquote(s) for s in parsed.path.split("/") if s], parsed


# ---- ad -----------------------------------------------------------------------------

def resolve_ad(value):
    """Bare item id or an avito.ru ad link -> the numeric id (int)."""
    value = (value or "").strip()
    if ITEM_ID_RE.match(value):
        return int(value)
    if _is_link(value):
        segments, _ = _parse_link(value)
        if segments:
            last = segments[-1]
            if ITEM_ID_RE.match(last):
                return int(last)
            match = _PATH_ITEM_RE.search(last)
            if match:
                return int(match.group(1))
        raise ValueError("Must be an avito.ru ad link "
                         "(https://www.avito.ru/<city>/<category>/<title>_<id>).")
    raise ValueError("Must be a numeric Avito ad id (7726049894) or an avito.ru ad link.")


def ad_link(path_or_id):
    """Canonical public link of an ad from its urlPath (tracking `context`
    query dropped) or its id."""
    if path_or_id is None or path_or_id == "":
        return None
    if isinstance(path_or_id, int) or str(path_or_id).isdigit():
        return f"{SITE}/{path_or_id}"
    path = str(path_or_id).split("?", 1)[0].split("#", 1)[0]
    if path.startswith("http"):
        return path
    return SITE + (path if path.startswith("/") else "/" + path)


# ---- seller ---------------------------------------------------------------------------

def resolve_seller(value):
    """A seller reference -> {"kind": "brand" | "key" | "hash", "id": str}.

    brand  /brands/<slug> profile (shop slug, i<user id>, private hash slug)
    key    the 32-hex profile key (/user/<key>/profile)
    hash   a bare 32-hex value: a profile key or a private brand slug
           (api.py tries both)."""
    value = (value or "").strip()
    if _is_link(value):
        segments, _ = _parse_link(value)
        if len(segments) >= 2 and segments[0] == "brands" and SLUG_RE.match(segments[1].lower()):
            return {"kind": "brand", "id": segments[1].lower()}
        if len(segments) >= 2 and segments[0] == "user" and HEX32_RE.match(segments[1].lower()):
            return {"kind": "key", "id": segments[1].lower()}
        raise ValueError("Must be an avito.ru seller profile link "
                         "(https://www.avito.ru/brands/<seller> or /user/<key>/profile).")
    low = value.lower()
    if HEX32_RE.match(low):
        return {"kind": "hash", "id": low}
    if SLUG_RE.match(low):
        return {"kind": "brand", "id": low}
    raise ValueError("Must be an Avito seller id (the profile slug such as americanauto "
                     "or i13285073, or the 32-character profile key) or an avito.ru profile link.")


def seller_link(slug_or_path):
    if not slug_or_path:
        return None
    text = str(slug_or_path).split("?", 1)[0]
    if text.startswith("http"):
        return text
    if text.startswith("/"):
        return SITE + text
    return f"{SITE}/brands/{text}"


def seller_page_path(ref):
    """The profile page path for a resolved seller ref of kind brand / key."""
    if ref["kind"] == "key":
        return f"/user/{ref['id']}/profile"
    return f"/brands/{ref['id']}"


# ---- location -------------------------------------------------------------------------

def resolve_location(value):
    """A location reference -> {"id": int} | {"slug": str} | {"name": str}."""
    value = (value or "").strip()
    if value.isdigit() and 1 <= len(value) <= 9:
        return {"id": int(value)}
    if _is_link(value):
        segments, _ = _parse_link(value)
        if not segments or segments[0] in _NON_LOCATION_SEGMENTS:
            raise ValueError("Must be an avito.ru location or listing link "
                             "(https://www.avito.ru/kazan or https://www.avito.ru/kazan/avtomobili).")
        slug = segments[0].lower()
        if slug == ALL_RUSSIA_SLUG:
            return {"id": ALL_RUSSIA_ID}
        if not _LATIN_SLUG_RE.match(slug):
            raise ValueError("Must be an avito.ru location link.")
        return {"id": LOCATION_SLUGS[slug]} if slug in LOCATION_SLUGS else {"slug": slug}
    low = value.lower()
    if low in (ALL_RUSSIA_SLUG, "russia", "россия", "вся россия", "все регионы"):
        return {"id": ALL_RUSSIA_ID}
    if _LATIN_SLUG_RE.match(low):
        return {"id": LOCATION_SLUGS[low]} if low in LOCATION_SLUGS else {"slug": low}
    if 2 <= len(value) <= 100:
        return {"name": value}
    raise ValueError("Must be an Avito location id (637640), a place name (Казань), "
                     "a location slug (kazan) or an avito.ru location link.")


# ---- category -------------------------------------------------------------------------

def resolve_category(value):
    """A category reference -> {"id": int} | {"slug": str}."""
    value = (value or "").strip()
    if value.isdigit() and 1 <= len(value) <= 6:
        return {"id": int(value)}
    if _is_link(value):
        segments, _ = _parse_link(value)
        if len(segments) >= 2 and segments[0] not in _NON_LOCATION_SEGMENTS:
            # "/kazan/avtomobili/bmw-ASgB..." -> "avtomobili". The site's
            # filter hash ("-ASgB...") rides on a later segment or on the
            # category segment itself; it is dropped (the JSON search does
            # not accept it — verified 2026-10-24).
            slug = segments[1].split("-ASg", 1)[0].lower()
            if SLUG_RE.match(slug):
                return {"slug": slug}
        raise ValueError("Must be an avito.ru listing link "
                         "(https://www.avito.ru/<city>/<category>, e.g. https://www.avito.ru/moskva/avtomobili).")
    low = value.lower()
    if SLUG_RE.match(low):
        return {"slug": low}
    raise ValueError("Must be an Avito category id (9), a category slug (avtomobili) "
                     "or an avito.ru listing link.")


def category_slug(url):
    """'/all/avtomobili?cd=1' or '/moskva/avtomobili/...' -> 'avtomobili'."""
    if not url:
        return None
    path = str(url).split("?", 1)[0]
    segments = [s for s in path.split("/") if s]
    if len(segments) < 2:
        return None
    slug = segments[1]
    return slug if SLUG_RE.match(slug) else None


# ---- filters --------------------------------------------------------------------------
# The `filters` input: comma-separated "<attribute id>:<value>" pairs, the
# ids the site uses in its own params[...] query (filtersV2 vocabulary,
# returned by /avito/ads/search as `filters`):
#
#   110007:331253              one value          -> params[110007]=331253
#   110008:331255|331257       several values     -> params[110008][]=331255&params[110008][]=331257
#   2687:-50000                numeric range      -> params[2687][to]=50000
#   164669:2018-2022           numeric range      -> params[164669][from]=2018&params[164669][to]=2022
#
# Verified against /web/1/js/items 2026-10-24 (the response `url` re-encodes
# each form as the site's own filter hash).
_FILTER_PAIR_RE = re.compile(r"^([0-9]{1,12}):(.+)$")
_RANGE_RE = re.compile(r"^([0-9]+(?:\.[0-9]+)?)?-([0-9]+(?:\.[0-9]+)?)?$")
_VALUE_RE = re.compile(r"^[0-9]{1,12}$")
MAX_FILTERS = 20


def parse_filters(value):
    """'110007:331253,2687:-50000' -> a list of (query key, value) pairs for
    /web/1/js/items. ValueError with the offending pair otherwise."""
    if value is None:
        return []
    pairs = [p.strip() for p in str(value).split(",") if p.strip()]
    if len(pairs) > MAX_FILTERS:
        raise ValueError(f"At most {MAX_FILTERS} filters.")
    out = []
    for pair in pairs:
        match = _FILTER_PAIR_RE.match(pair)
        if not match:
            raise ValueError(f"'{pair}' is not <attribute id>:<value> (e.g. 110007:331253).")
        attr, raw = match.group(1), match.group(2).strip()
        rng = _RANGE_RE.match(raw)
        if rng and "-" in raw:
            lo, hi = rng.group(1), rng.group(2)
            if lo is None and hi is None:
                raise ValueError(f"'{pair}': a range needs a lower or an upper bound.")
            if lo is not None:
                out.append((f"params[{attr}][from]", lo))
            if hi is not None:
                out.append((f"params[{attr}][to]", hi))
            continue
        values = [v.strip() for v in raw.split("|") if v.strip()]
        if not values or not all(_VALUE_RE.match(v) for v in values):
            raise ValueError(f"'{pair}': values are numeric value ids "
                             "(several joined with |) or a min-max range.")
        if len(values) == 1:
            out.append((f"params[{attr}]", values[0]))
        else:
            out.extend((f"params[{attr}][]", v) for v in values)
    return out
