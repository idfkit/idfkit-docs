"""Utilities for loading EnergyPlus schema metadata from idfkit.

Provides the data structures and functions behind the inline field metadata
pills in the IO Reference (build-time HTML injection). The IDF editor's hover
documentation does not use them: it reads the published @idfkit/schemas
package in the browser.

Replaces custom IDD parsers by delegating to idfkit's bundled epJSON schemas.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from idfkit import get_schema
from idfkit.schema import EpJSONSchema

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class DocFieldInfo:
    """Field metadata for documentation rendering.

    Populated from idfkit's epJSON schema for the inline pill generator
    (markdown_postprocessor).
    """

    name: str  # Human-readable display name (e.g. "Thermal Absorptance")
    snake_name: str  # Schema key (e.g. "thermal_absorptance")
    field_type: str = ""  # IDD-style: real, integer, alpha, choice, object-list, external-list
    units: str = ""
    ip_units: str = ""
    default: str = ""
    minimum: str = ""
    minimum_exclusive: bool = False
    maximum: str = ""
    maximum_exclusive: bool = False
    required: bool = False
    autosizable: bool = False
    autocalculatable: bool = False
    keys: list[str] = field(default_factory=list)


@dataclass
class DocObjectInfo:
    """Object-level schema metadata with field lookup by display name."""

    name: str  # Original case (e.g. "Pump:ConstantSpeed")
    fields: list[DocFieldInfo] = field(default_factory=list)
    fields_by_display_name: dict[str, DocFieldInfo] = field(default_factory=dict, repr=False)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _version_tag_to_tuple(version_tag: str) -> tuple[int, int, int]:
    """Convert ``'v25.2.0'`` to ``(25, 2, 0)``."""
    parts = version_tag.lstrip("v").split(".")
    return (int(parts[0]), int(parts[1]), int(parts[2]))


def _detect_auto_flags(field_schema: dict[str, Any]) -> tuple[bool, bool]:
    """Return ``(autosizable, autocalculatable)`` from *anyOf* patterns."""
    autosizable = False
    autocalculatable = False
    for sub in field_schema.get("anyOf", []):
        if sub.get("type") == "string":
            enum_vals = sub.get("enum", [])
            if "Autosize" in enum_vals:
                autosizable = True
            if "Autocalculate" in enum_vals:
                autocalculatable = True
    return autosizable, autocalculatable


def _resolve_anyof_type(any_of: list[dict[str, Any]]) -> str | None:
    """Resolve an IDD type from an ``anyOf`` schema (autosizable/autocalculatable)."""
    for sub in any_of:
        if sub.get("type") in ("number", "integer"):
            return "integer" if sub["type"] == "integer" else "real"
    if any(sub.get("enum") for sub in any_of if sub.get("type") == "string"):
        return "choice"
    return None


def _resolve_string_subtype(field_schema: dict[str, Any]) -> str:
    """Classify a JSON ``"string"`` field into an IDD type."""
    if "object_list" in field_schema:
        return "object-list"
    if field_schema.get("data_type") == "external_list":
        return "external-list"
    return "alpha"


_JSON_TYPE_MAP: dict[str, str] = {"number": "real", "integer": "integer"}


def _resolve_idd_type(field_schema: dict[str, Any]) -> str:
    """Map an epJSON field schema to an IDD-style type string."""
    if "enum" in field_schema:
        return "choice"

    any_of: list[dict[str, Any]] = field_schema.get("anyOf", [])
    if any_of:
        return _resolve_anyof_type(any_of) or "alpha"

    json_type = field_schema.get("type", "string")
    if json_type in _JSON_TYPE_MAP:
        return _JSON_TYPE_MAP[json_type]
    if json_type == "string":
        return _resolve_string_subtype(field_schema)
    return "alpha"


_CHOICE_EXCLUDE = {"", "Autosize", "Autocalculate"}


def _extract_choices(field_schema: dict[str, Any]) -> list[str]:
    """Extract enum/choice values, filtering out blanks and Autosize/Autocalculate markers."""
    raw: list[str] = list(field_schema.get("enum", []))
    if not raw:
        for sub in field_schema.get("anyOf", []):
            if sub.get("type") == "string" and "enum" in sub:
                raw.extend(sub["enum"])
    return [v for v in raw if v not in _CHOICE_EXCLUDE]


def _build_doc_field(
    snake_name: str,
    schema: EpJSONSchema,
    obj_type: str,
    field_info_map: dict[str, Any],
    required_set: set[str],
) -> DocFieldInfo:
    """Build a single ``DocFieldInfo`` from the epJSON schema."""
    field_schema: dict[str, Any] = schema.get_field_schema(obj_type, snake_name) or {}
    fi_entry = field_info_map.get(snake_name, {})
    display_name: str = fi_entry.get("field_name", snake_name)

    autosizable, autocalculatable = _detect_auto_flags(field_schema)
    idd_type = _resolve_idd_type(field_schema)

    # Bounds -- older epJSON schemas (v8.9-v9.5) use boolean values for
    # min/max (e.g. "minimum": true) instead of numeric bounds. The
    # isinstance guards skip these so they don't break float() conversion.
    minimum_val = ""
    minimum_exclusive = False
    maximum_val = ""
    maximum_exclusive = False

    if (
        "exclusiveMinimum" in field_schema
        and isinstance(field_schema["exclusiveMinimum"], (int, float))
        and not isinstance(field_schema["exclusiveMinimum"], bool)
    ):
        minimum_val = str(field_schema["exclusiveMinimum"])
        minimum_exclusive = True
    elif (
        "minimum" in field_schema
        and isinstance(field_schema["minimum"], (int, float))
        and not isinstance(field_schema["minimum"], bool)
    ):
        minimum_val = str(field_schema["minimum"])

    if (
        "exclusiveMaximum" in field_schema
        and isinstance(field_schema["exclusiveMaximum"], (int, float))
        and not isinstance(field_schema["exclusiveMaximum"], bool)
    ):
        maximum_val = str(field_schema["exclusiveMaximum"])
        maximum_exclusive = True
    elif (
        "maximum" in field_schema
        and isinstance(field_schema["maximum"], (int, float))
        and not isinstance(field_schema["maximum"], bool)
    ):
        maximum_val = str(field_schema["maximum"])

    # Default
    default_val = ""
    if "default" in field_schema:
        default_val = str(field_schema["default"])

    return DocFieldInfo(
        name=display_name,
        snake_name=snake_name,
        field_type=idd_type,
        units=field_schema.get("units", ""),
        ip_units=field_schema.get("ip-units", ""),
        default=default_val,
        minimum=minimum_val,
        minimum_exclusive=minimum_exclusive,
        maximum=maximum_val,
        maximum_exclusive=maximum_exclusive,
        required=snake_name in required_set,
        autosizable=autosizable,
        autocalculatable=autocalculatable,
        keys=_extract_choices(field_schema),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_object_index(version_tag: str) -> dict[str, DocObjectInfo]:
    """Load the epJSON schema for *version_tag* and build the full object index.

    Args:
        version_tag: Version string such as ``"v25.2.0"``.

    Returns:
        Mapping of object type names (original case) to :class:`DocObjectInfo`.
    """
    version_tuple = _version_tag_to_tuple(version_tag)
    schema = get_schema(version_tuple)
    logger.info(
        "Loaded epJSON schema for %s (%d object types)",
        version_tag,
        len(schema),
    )

    index: dict[str, DocObjectInfo] = {}

    for obj_type in schema.object_types:
        obj_schema = schema.get_object_schema(obj_type)
        if not obj_schema:
            continue

        legacy: dict[str, Any] = obj_schema.get("legacy_idd", {})
        field_info_map: dict[str, Any] = legacy.get("field_info", {})
        all_field_names: list[str] = legacy.get("fields", [])

        # Required fields
        inner = schema.get_inner_schema(obj_type)
        required_set: set[str] = set(inner.get("required", [])) if inner else set()

        # Build per-field metadata
        doc_fields: list[DocFieldInfo] = []
        fields_by_display: dict[str, DocFieldInfo] = {}

        for snake_name in all_field_names:
            doc_field = _build_doc_field(snake_name, schema, obj_type, field_info_map, required_set)
            doc_fields.append(doc_field)
            fields_by_display[doc_field.name.lower()] = doc_field

        index[obj_type] = DocObjectInfo(
            name=obj_type,
            fields=doc_fields,
            fields_by_display_name=fields_by_display,
        )

    return index
