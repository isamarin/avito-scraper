"""Shared marshmallow request fields + schema helpers for the routes.

avito/schemas.py composes its route schemas from these:

  * whitespace-stripped strings, empty == missing
  * booleans as true/false | 1/0 | yes/no flags
  * ONE param per input — a `RefField` subclass accepts a bare id OR a full
    site link and hands the raw string to a site-specific `resolver`
    (never a sibling `url`/`id` pair)
  * choice params are case-insensitive and may map to upstream tokens
  * unknown query params are rejected (BaseSchema) so typos surface as 400s

`load_query(SchemaCls, query_dict)` -> (data, None) | (None, 400 body).
"""
from marshmallow import RAISE, Schema, ValidationError, fields, validate

__all__ = [
    "BaseSchema", "load_query",
    "StrippedString", "QueryField", "Flag", "RefField",
    "PageField", "PageSizeField", "LimitField", "PositiveInt", "ChoiceField",
]

_TRUE = {"true", "1", "yes", "y", "on"}
_FALSE = {"false", "0", "no", "n", "off", ""}


# ---- schema + loading --------------------------------------------------------

class BaseSchema(Schema):
    """Unknown query params are rejected (a typo must not silently no-op)."""

    class Meta:
        unknown = RAISE


def load_query(schema_cls, query):
    """Validate a query dict. Returns (data, None) or (None, body) where body
    is {"error": "Invalid parameters: …", "errors": {field: [msgs]}} for a 400."""
    try:
        return schema_cls().load(query), None
    except ValidationError as e:
        messages = e.normalized_messages()
        flat = "; ".join(f"{k}: {' '.join(v) if isinstance(v, list) else v}" for k, v in messages.items())
        return None, {"error": f"Invalid parameters: {flat}", "errors": messages}


# ---- strings -----------------------------------------------------------------

class StrippedString(fields.String):
    """String with whitespace collapsed; empty -> error when required, else None."""

    def _deserialize(self, value, attr, data, **kwargs):
        value = super()._deserialize(value, attr, data, **kwargs)
        value = " ".join(value.split())
        if not value:
            if self.required:
                raise ValidationError("Must not be empty.")
            return None
        return value


class QueryField(StrippedString):
    """Free-text search term, required, 1-200 chars by default."""

    def __init__(self, max_length=200, **kwargs):
        kwargs.setdefault("required", True)
        kwargs.setdefault("validate", validate.Length(min=1, max=max_length))
        super().__init__(**kwargs)


class RefField(StrippedString):
    """ONE param that accepts a bare id OR a full site link. Subclasses set
    `resolver` (a function raising ValueError with a user-facing message) or
    pass `resolver=` at construction:

        class ProductRefField(RefField):
            resolver = staticmethod(refs.resolve_product_ref)
    """
    resolver = None

    def __init__(self, resolver=None, **kwargs):
        kwargs.setdefault("required", True)
        super().__init__(**kwargs)
        if resolver is not None:
            self._resolver = resolver
        else:
            self._resolver = type(self).resolver

    def _deserialize(self, value, attr, data, **kwargs):
        value = super()._deserialize(value, attr, data, **kwargs)
        if value is None:
            return None
        if self._resolver is None:
            return value
        try:
            return self._resolver(value)
        except ValueError as e:
            raise ValidationError(str(e))


# ---- booleans ----------------------------------------------------------------

class Flag(fields.Field):
    """Boolean query flag: true/false, 1/0, yes/no, on/off (case-insensitive).
    Defaults to None (= "not specified") unless load_default is given."""

    def __init__(self, **kwargs):
        kwargs.setdefault("load_default", None)
        super().__init__(**kwargs)

    def _deserialize(self, value, attr, data, **kwargs):
        if isinstance(value, bool):
            return value
        low = str(value).strip().lower()
        if low in _TRUE:
            return True
        if low in _FALSE:
            return False
        raise ValidationError("Must be true or false.")


# ---- numbers / pagination ----------------------------------------------------

class PageField(fields.Integer):
    """1-based page, default 1, capped at max_page."""

    def __init__(self, max_page=100, **kwargs):
        kwargs.setdefault("load_default", 1)
        kwargs.setdefault("validate", validate.Range(min=1, max=max_page))
        super().__init__(strict=False, **kwargs)


class PageSizeField(fields.Integer):
    def __init__(self, default=10, max_size=50, **kwargs):
        kwargs.setdefault("load_default", default)
        kwargs.setdefault("validate", validate.Range(min=1, max=max_size))
        super().__init__(strict=False, **kwargs)


class LimitField(PageSizeField):
    """Maximum number of results (default 10, max 50 unless overridden)."""


class PositiveInt(fields.Integer):
    """Optional integer >= 1 (counts, quantities, ids given as numbers)."""

    def __init__(self, max_value=None, **kwargs):
        kwargs.setdefault("load_default", None)
        kwargs.setdefault("validate", validate.Range(min=1, max=max_value))
        super().__init__(strict=False, **kwargs)


# ---- choices ---------------------------------------------------------------

class ChoiceField(StrippedString):
    """Case-insensitive choice. `choices` is a list of public values, OR a
    dict {public value: upstream token} in which case the mapped token is
    returned (rapidapi MappedField). Optional by default."""

    def __init__(self, choices, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("load_default", None)
        super().__init__(**kwargs)
        self.value_map = dict(choices) if isinstance(choices, dict) else None
        self.choices = [str(c).lower() for c in (choices.keys() if isinstance(choices, dict) else choices)]
        self._lookup = {c.lower(): c for c in (choices.keys() if isinstance(choices, dict) else choices)}

    def _deserialize(self, value, attr, data, **kwargs):
        value = super()._deserialize(value, attr, data, **kwargs)
        if value is None:
            return None
        key = self._lookup.get(value.lower())
        if key is None:
            raise ValidationError(f"Must be one of: {', '.join(self.choices)}.")
        return self.value_map[key] if self.value_map is not None else str(key).lower()
