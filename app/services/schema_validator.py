from typing import Any
from jsonschema import Draft202012Validator


def validate_schema(instance: Any, schema: dict) -> list[str]:
    """Return a list of human-readable validation errors ([] == valid)."""
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    return [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors]
