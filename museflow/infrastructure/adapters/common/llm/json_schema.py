from typing import Final

from pydantic import BaseModel

# Gemini rejects a response schema with an enum above ~100 values (400 INVALID_ARGUMENT), counting each enum on its own
MAX_ENUM_VALUES: Final[int] = 100


class JsonSchemaProperty(BaseModel):
    """A JSON Schema node, built to satisfy strict structured outputs on every model family.

    Strict mode requires every object to list all its properties as required and to forbid extra ones: `object()`
    does both, so an optional field is expressed as a nullable type (`string(nullable=True)`) rather than omitted.

    Portability rules, learnt from provider rejections: an enum holds at most `MAX_ENUM_VALUES` values (split a larger
    vocabulary across fields, since Gemini also sums the values of `anyOf` branches), and a nullable enum is
    `anyOf [enum, null]` (Anthropic rejects `type: [string, null]` with an `enum`).
    """

    type: str | list[str] | None = None
    anyOf: list[JsonSchemaProperty] | None = None
    items: JsonSchemaProperty | None = None
    properties: dict[str, JsonSchemaProperty] | None = None
    required: list[str] | None = None
    additionalProperties: bool | None = None
    enum: list[str] | None = None

    @classmethod
    def string(cls, *, nullable: bool = False) -> JsonSchemaProperty:
        return cls(type=["string", "null"] if nullable else "string")

    @classmethod
    def enum_string(cls, values: list[str], *, nullable: bool = False) -> JsonSchemaProperty:
        if len(values) > MAX_ENUM_VALUES:
            raise ValueError(f"An enum holds at most {MAX_ENUM_VALUES} values, got {len(values)}: split it")

        enum = cls(type="string", enum=values)
        return cls(anyOf=[enum, cls(type="null")]) if nullable else enum

    @classmethod
    def number(cls) -> JsonSchemaProperty:
        return cls(type="number")

    @classmethod
    def integer(cls) -> JsonSchemaProperty:
        return cls(type="integer")

    @classmethod
    def array(cls, items: JsonSchemaProperty) -> JsonSchemaProperty:
        return cls(type="array", items=items)

    @classmethod
    def object(cls, properties: dict[str, JsonSchemaProperty], *, nullable: bool = False) -> JsonSchemaProperty:
        return cls(
            type=["object", "null"] if nullable else "object",
            properties=properties,
            required=list(properties),
            additionalProperties=False,
        )
