from pydantic import BaseModel


class JsonSchemaProperty(BaseModel):
    """A JSON Schema node, built to satisfy strict structured outputs on every model family.

    Strict mode requires every object to list all its properties as required and to forbid extra ones: `object()`
    does both, so an optional field is expressed as a nullable type (`string(nullable=True)`) rather than omitted.

    A nullable enum is `anyOf [enum, null]`: Anthropic rejects `type: [string, null]` with an `enum`.
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
