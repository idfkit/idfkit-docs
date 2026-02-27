"""Parser for EnergyPlus IDD (Input Data Dictionary) files.

Extracts structured metadata for each IDF object and its fields,
including types, units, defaults, ranges, choices, and flags.
"""

from __future__ import annotations

import logging
import re

from scripts.models import IddField, IddObject

logger = logging.getLogger(__name__)


def parse_idd(idd_text: str) -> dict[str, IddObject]:
    """Parse an Energy+.idd.in file into a dict mapping object names to IddObject.

    Args:
        idd_text: Full text content of the IDD file.

    Returns:
        Dictionary mapping object names (e.g., "Pump:ConstantSpeed") to their
        IddObject definitions with all field metadata.
    """
    # Strip comment-only lines (starting with !) but keep inline \-directives
    lines = idd_text.splitlines()
    cleaned_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("!"):
            continue
        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)

    # Split into object blocks. Each object ends with a semicolon on its last field.
    # Objects are separated by their name line (a line starting with a letter and ending with comma).
    objects = _split_objects(text)

    result: dict[str, IddObject] = {}
    for obj_text in objects:
        obj = _parse_object(obj_text)
        if obj:
            result[obj.name] = obj

    logger.info("Parsed %d IDD objects", len(result))
    return result


def _split_objects(text: str) -> list[str]:
    """Split IDD text into individual object definition blocks."""
    # An object starts with a line like "ObjectName," or "Object:SubName,"
    # at the beginning of a line (no leading whitespace).
    # We split on these boundaries.
    object_pattern = re.compile(r"^([A-Z][A-Za-z0-9:_\- ]*),\s*$", re.MULTILINE)

    objects: list[str] = []
    matches = list(object_pattern.finditer(text))

    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        objects.append(text[start:end].strip())

    return objects


def _parse_object(obj_text: str) -> IddObject | None:
    """Parse a single IDD object block into an IddObject."""
    lines = obj_text.split("\n")
    if not lines:
        return None

    # First line is "ObjectName,"
    obj_name = lines[0].strip().rstrip(",").strip()
    if not obj_name:
        return None

    memo_parts: list[str] = []
    fields = _parse_object_fields(lines[1:], memo_parts)

    # Build fields_by_name lookup (case-insensitive on the field name)
    fields_by_name: dict[str, IddField] = {f.name.lower(): f for f in fields if f.name}

    return IddObject(
        name=obj_name,
        memo=" ".join(memo_parts),
        fields=fields,
        fields_by_name=fields_by_name,
    )


def _parse_object_fields(lines: list[str], memo_parts: list[str]) -> list[IddField]:
    """Parse field definitions from an object's body lines."""
    fields: list[IddField] = []
    current_field: IddField | None = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Object-level directives (before first field)
        if stripped.startswith("\\") and current_field is None:
            _parse_object_directive(stripped, memo_parts)
            continue

        # Field definition line: "A1," or "N2," or "A1;" etc.
        field_match = re.match(r"^([AN]\d+)\s*[,;]", stripped)
        if field_match:
            if current_field is not None:
                fields.append(current_field)
            current_field = IddField(name="", field_id=field_match.group(1))
            inline = stripped[field_match.end() :].strip()
            if inline:
                _parse_field_directive(inline, current_field)
            continue

        # Field-level directives
        if stripped.startswith("\\") and current_field is not None:
            _parse_field_directive(stripped, current_field)

    if current_field is not None:
        fields.append(current_field)
    return fields


def _parse_object_directive(text: str, memo_parts: list[str]) -> None:
    """Parse an object-level directive like \\memo, \\unique-object, etc."""
    if text.startswith("\\memo"):
        memo_parts.append(text[len("\\memo") :].strip())


def _parse_field_directive(text: str, field: IddField) -> None:
    """Parse a field-level directive and update the IddField."""
    if text.startswith("\\field"):
        field.name = text[len("\\field") :].strip()
    elif text.startswith("\\type"):
        field.field_type = text[len("\\type") :].strip().lower()
    elif text.startswith("\\units") and not text.startswith("\\unitsBasedOnField"):
        field.units = text[len("\\units") :].strip()
    elif text.startswith("\\ip-units"):
        field.ip_units = text[len("\\ip-units") :].strip()
    elif text.startswith("\\default"):
        field.default = text[len("\\default") :].strip()
    elif text.startswith("\\minimum"):
        _parse_bound_directive(text, "\\minimum", field, is_min=True)
    elif text.startswith("\\maximum"):
        _parse_bound_directive(text, "\\maximum", field, is_min=False)
    else:
        _parse_field_flag_directive(text, field)


def _parse_bound_directive(text: str, prefix: str, field: IddField, *, is_min: bool) -> None:
    """Parse \\minimum or \\maximum directives, including exclusive variants (> or <)."""
    exclusive = len(text) > len(prefix) and text[len(prefix)] in "<>"
    directive = prefix + text[len(prefix)] if exclusive else prefix
    value = text[len(directive) :].strip()
    if is_min:
        field.minimum = value
        field.minimum_exclusive = exclusive
    else:
        field.maximum = value
        field.maximum_exclusive = exclusive


def _parse_field_flag_directive(text: str, field: IddField) -> None:
    """Parse flag and list directives (required, autosizable, key, note, etc.)."""
    if text.startswith("\\required-field"):
        field.required = True
    elif text.startswith("\\autosizable"):
        field.autosizable = True
    elif text.startswith("\\autocalculatable"):
        field.autocalculatable = True
    elif text.startswith("\\key"):
        key_value = text[len("\\key") :].strip()
        if key_value:
            field.keys.append(key_value)
    elif text.startswith("\\note"):
        note_text = text[len("\\note") :].strip()
        field.notes = f"{field.notes} {note_text}" if field.notes else note_text
