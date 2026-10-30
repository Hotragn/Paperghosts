"""Atlas $jsonSchema validators, generated from the Pydantic models so the two can't drift apart
(ARCHITECTURE section 4). Atlas reads JSON Schema draft 4 with bsonType, and has no $ref, const,
format or integer type, so Pydantic's schema is rewritten for it."""

from pydantic import BaseModel

TYPES = {
    "string": "string",
    "integer": ["int", "long"],
    "number": "number",
    "boolean": "bool",
    "object": "object",
    "array": "array",
    "null": "null",
}
DROPPED = {"title", "description", "default", "examples"}
KEPT = {
    "bsonType", "enum", "required", "additionalProperties", "minItems", "maxItems",
    "minLength", "maxLength", "pattern", "minimum", "maximum", "multipleOf",
}  # fmt: skip


def validator(model: type[BaseModel]) -> dict:
    """The collection validator for model's documents, as stored with by_alias."""
    schema = model.model_json_schema(by_alias=True)
    defs = schema.pop("$defs", {})
    return {"$jsonSchema": convert(schema, defs)}


def convert(schema: dict, defs: dict) -> dict:
    if "$ref" in schema:
        target = defs[schema["$ref"].rsplit("/", 1)[1]]
        rest = {k: v for k, v in schema.items() if k != "$ref"}
        return convert(target, defs) | convert(rest, defs)
    out = {}
    for key, value in schema.items():
        if key in DROPPED:
            continue
        if key == "type":
            out["bsonType"] = TYPES[value]
        elif key == "const":
            out["enum"] = [value]
        elif key == "properties":
            out[key] = {name: convert(field, defs) for name, field in value.items()}
        elif key == "prefixItems":  # a tuple
            out["items"] = [convert(item, defs) for item in value]
            out["additionalItems"] = False
        elif key in ("items", "additionalProperties") and isinstance(value, dict):
            out[key] = convert(value, defs)
        elif key == "anyOf":
            options = [convert(option, defs) for option in value]
            if all(option.keys() == {"bsonType"} for option in options):
                # a plain union of types, such as str | None, is one bsonType list
                types = []
                for option in options:
                    found = option["bsonType"]
                    types += [found] if isinstance(found, str) else found
                out["bsonType"] = types
            else:
                out["anyOf"] = options
        elif key in KEPT:
            out[key] = value
        else:
            raise ValueError(f"Atlas's $jsonSchema has no {key!r}")
    return out
