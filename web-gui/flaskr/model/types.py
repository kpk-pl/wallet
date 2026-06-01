from typing import Annotated
from decimal import Decimal
from bson.objectid import ObjectId
from bson.decimal128 import Decimal128
from pydantic import HttpUrl, TypeAdapter
from pydantic.functional_validators import BeforeValidator
from pydantic_core import core_schema


class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        return core_schema.no_info_plain_validator_function(
            cls.validate,
            serialization=core_schema.plain_serializer_function_ser_schema(
                str, when_used="json"
            ),
        )

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema_obj, handler):
        return {"type": "string"}


_http_url_adapter = TypeAdapter(HttpUrl)


def _validate_url_str(value):
    # Pydantic v2's HttpUrl validates to a `Url` object and *normalizes* the
    # string (e.g. appends a trailing slash to a bare host). Templates, quote
    # fetchers, Mongo storage and `json.dumps` all expect plain strings, and
    # v1 stored the URL verbatim — so validate as a URL but keep the original
    # string untouched.
    if isinstance(value, str):
        _http_url_adapter.validate_python(value)
    return value


# A `str` field constrained to be a valid HTTP(S) URL, stored verbatim.
HttpUrlStr = Annotated[str, BeforeValidator(_validate_url_str)]


def _coerce_decimal(value):
    # MongoDB stores Decimals as `Decimal128`. Pydantic v1 accepted it (it
    # stringified unknown inputs); v2's Decimal validator only accepts
    # int/float/str/Decimal, so convert it back to a plain Decimal here.
    if isinstance(value, Decimal128):
        return value.to_decimal()
    return value


# A Decimal field that also accepts BSON `Decimal128` values straight from Mongo.
BsonDecimal = Annotated[Decimal, BeforeValidator(_coerce_decimal)]
