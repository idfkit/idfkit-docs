"""Build a compact IDD schema JSON for the Monaco hover documentation provider.

Parses the EnergyPlus IDD (Input Data Dictionary) file and produces a compact
JSON file containing object type definitions, field metadata, and documentation
text.  This JSON is loaded by the browser-side IDF editor to power hover
tooltips.

The parser handles the standard IDD format:

    \\group Group Name

    ClassName,
        \\memo Description of the object
        \\unique-object
        \\min-fields 5
      A1 , \\field Field Name
           \\required-field
           \\type choice
           \\key Option1
           \\key Option2
      N1 ; \\field Field Name
           \\type real
           \\units W
           \\minimum 0.0
           \\default 1.0
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

FIELD_TYPE_MAP: dict[str, str] = {
    "real": "real",
    "integer": "integer",
    "alpha": "alpha",
    "choice": "choice",
    "object-list": "object-list",
    "external-list": "external-list",
    "node": "node",
}


@dataclass
class CompactField:
    id: str
    name: str = ""
    type: str = "alpha"
    required: bool = False
    default: str | None = None
    units: str | None = None
    minimum: float | None = None
    exclusive_minimum: bool = False
    maximum: float | None = None
    exclusive_maximum: bool = False
    choices: list[str] = field(default_factory=list)
    memo: str = ""
    autosizable: bool = False
    autocalculatable: bool = False

    def to_dict(self) -> dict:
        d: dict = {"id": self.id, "name": self.name, "type": self.type, "required": self.required, "memo": self.memo}
        if self.default is not None:
            d["default"] = self.default
        if self.units:
            d["units"] = self.units
        if self.minimum is not None:
            d["minimum"] = self.minimum
            if self.exclusive_minimum:
                d["exclusiveMinimum"] = True
        if self.maximum is not None:
            d["maximum"] = self.maximum
            if self.exclusive_maximum:
                d["exclusiveMaximum"] = True
        if self.choices:
            d["choices"] = self.choices
        d["autosizable"] = self.autosizable
        d["autocalculatable"] = self.autocalculatable
        return d


@dataclass
class CompactObjectType:
    name: str
    group: str = ""
    memo: str = ""
    fields: list[CompactField] = field(default_factory=list)
    min_fields: int = 0
    is_unique: bool = False
    is_required: bool = False
    extensible: int = 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "group": self.group,
            "memo": self.memo,
            "fields": [f.to_dict() for f in self.fields],
            "minFields": self.min_fields,
            "isUnique": self.is_unique,
            "isRequired": self.is_required,
            "extensible": self.extensible,
        }


# ---------------------------------------------------------------------------
# IDD parser
# ---------------------------------------------------------------------------

_PROPERTY_RE = re.compile(r"\\(\S+)\s*(.*)")
_FIELD_ID_RE = re.compile(r"^\s*([AN]\d+)\s*[,;]")
_CLASS_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9:_ -]*[,;]$")


def _strip_comments(line: str) -> str:
    """Remove inline comments and strip trailing whitespace."""
    pos = line.find("!")
    return line[:pos].rstrip() if pos >= 0 else line


def _is_class_name_line(stripped: str, raw_line: str) -> bool:
    """Determine if a line is a class name definition (not a field)."""
    if raw_line and raw_line[0] in (" ", "\t"):
        return False
    return bool(_CLASS_NAME_RE.match(stripped))


def _append_memo(existing: str, addition: str) -> str:
    """Append text to an existing memo string."""
    return (existing + " " + addition).strip() if existing else addition


def _apply_object_property(obj: CompactObjectType, fld: CompactField | None, name: str, value: str) -> bool:
    """Apply an object-level IDD property. Return True if handled."""
    if name == "memo":
        if fld is None:
            obj.memo = _append_memo(obj.memo, value)
        else:
            fld.memo = _append_memo(fld.memo, value)
        return True
    if name == "unique-object":
        obj.is_unique = True
        return True
    if name == "required-object":
        obj.is_required = True
        return True
    if name == "min-fields":
        with contextlib.suppress(ValueError):
            obj.min_fields = int(value)
        return True
    if name == "extensible":
        with contextlib.suppress(ValueError):
            obj.extensible = int(value.split(":")[0]) if ":" in value else int(value)
        return True
    return False


def _set_field_range(fld: CompactField, name: str, value: str) -> None:
    """Set a min/max range constraint on a field."""
    with contextlib.suppress(ValueError):
        if name.startswith("min"):
            fld.minimum = float(value)
            fld.exclusive_minimum = name == "minimum>"
        else:
            fld.maximum = float(value)
            fld.exclusive_maximum = name == "maximum<"


def _apply_field_property(fld: CompactField, name: str, value: str) -> None:
    """Apply a field-level IDD property."""
    # Simple flag properties
    _FIELD_FLAGS = {"required-field": "required", "autosizable": "autosizable", "autocalculatable": "autocalculatable"}
    if name in _FIELD_FLAGS:
        setattr(fld, _FIELD_FLAGS[name], True)
        return

    # Range properties
    if name in ("minimum", "minimum>", "maximum", "maximum<"):
        _set_field_range(fld, name, value)
        return

    # Value properties
    if name == "note":
        fld.memo = _append_memo(fld.memo, value)
    elif name == "field":
        fld.name = value
    elif name == "type":
        fld.type = FIELD_TYPE_MAP.get(value.lower(), value.lower())
    elif name == "key":
        fld.choices.append(value)
        if fld.type == "alpha":
            fld.type = "choice"
    elif name == "units":
        fld.units = value
    elif name == "default":
        fld.default = value


def _handle_property(state: dict, stripped: str) -> None:
    """Parse and apply a property line (\\name value)."""
    m = _PROPERTY_RE.match(stripped)
    if not m:
        return
    prop_name = m.group(1).lower()
    prop_value = m.group(2).strip()
    obj, fld = state["obj"], state["fld"]
    if (obj is not None and not _apply_object_property(obj, fld, prop_name, prop_value) and fld is not None) or (
        obj is None and fld is not None
    ):
        _apply_field_property(fld, prop_name, prop_value)


def _handle_class_name(state: dict, stripped: str) -> None:
    """Start a new object type definition."""
    if state["obj"] is not None:
        state["types"][state["obj"].name.lower()] = state["obj"]
    class_name = stripped.rstrip(",;").strip()
    state["obj"] = CompactObjectType(name=class_name, group=state["group"])
    state["fld"] = None


def _handle_field(state: dict, line: str) -> None:
    """Add a new field definition to the current object.

    IDD fields can have properties on the same line, e.g.:
        A1 , \\field Name of the Zone
    We parse the field ID first, then check for inline properties.
    """
    field_match = _FIELD_ID_RE.match(line)
    if not field_match or state["obj"] is None:
        return
    field_id = field_match.group(1)
    field_type = "alpha" if field_id.startswith("A") else "real"
    state["fld"] = CompactField(id=field_id, type=field_type)
    state["obj"].fields.append(state["fld"])

    # Check for inline properties after the comma/semicolon (e.g., \field Name)
    remainder = line[field_match.end() :].strip()
    if remainder.startswith("\\"):
        _handle_property(state, remainder)


def _process_line(line: str, raw_line: str, state: dict) -> None:
    """Process a single non-empty, non-comment IDD line."""
    stripped = line.strip()

    if stripped.startswith("\\group"):
        state["group"] = stripped[7:].strip()
    elif stripped.startswith("\\"):
        _handle_property(state, stripped)
    elif _is_class_name_line(stripped, raw_line):
        _handle_class_name(state, stripped)
    else:
        _handle_field(state, line)


def _iter_idd_lines(text: str) -> list[tuple[str, str]]:
    """Yield (processed_line, raw_line) tuples, skipping blanks, comments, and header."""
    result = []
    in_header = True
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if in_header:
            if line.startswith("!"):
                continue
            in_header = False
        if line.lstrip().startswith("!"):
            continue
        line = _strip_comments(line)
        if line.strip():
            result.append((line, raw_line))
    return result


def _extract_version(types: dict[str, CompactObjectType]) -> str:
    """Extract the EnergyPlus version from the parsed Version object."""
    if "version" not in types:
        return ""
    for f in types["version"].fields:
        if f.default:
            return f.default
    return ""


def parse_idd(idd_path: Path) -> dict:
    """Parse an EnergyPlus IDD file and return a compact schema dict.

    Returns a dict with keys ``version`` and ``objectTypes`` (keyed by
    lowercase class name).
    """
    text = idd_path.read_text(encoding="utf-8", errors="replace")
    state: dict = {"group": "", "obj": None, "fld": None, "types": {}}

    for line, raw_line in _iter_idd_lines(text):
        _process_line(line, raw_line, state)

    # Save the last object
    if state["obj"] is not None:
        state["types"][state["obj"].name.lower()] = state["obj"]

    version = _extract_version(state["types"])
    return {"version": version, "objectTypes": {k: v.to_dict() for k, v in state["types"].items()}}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_compact_schema(idd_path: Path, output_path: Path) -> bool:
    """Build a compact IDD schema JSON file from an EnergyPlus IDD file.

    Args:
        idd_path: Path to the Energy+.idd file.
        output_path: Path where the compact JSON will be written.

    Returns:
        True if the schema was built successfully, False otherwise.
    """
    if not idd_path.exists():
        logger.warning("IDD file not found: %s", idd_path)
        return False

    logger.info("Building compact IDD schema from %s", idd_path)
    schema = parse_idd(idd_path)

    obj_count = len(schema.get("objectTypes", {}))
    logger.info("Parsed %d object types (version: %s)", obj_count, schema.get("version", "unknown"))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, separators=(",", ":"))

    size_kb = output_path.stat().st_size / 1024
    logger.info("Wrote compact schema: %s (%.0f KB)", output_path, size_kb)
    return True


def find_idd_file(source_dir: Path) -> Path | None:
    """Search for the Energy+.idd file in an EnergyPlus source directory.

    Checks several known locations across different EnergyPlus versions.
    """
    candidates = [
        source_dir / "idd" / "Energy+.idd",
        source_dir / "idd" / "Energy+.idd.in",  # CMake template (source builds)
        source_dir / "idd" / "V8-9-0-Energy+.idd",  # v8.9 format
        source_dir / "Energy+.idd",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    # Glob for any .idd file in idd/ directory
    idd_dir = source_dir / "idd"
    if idd_dir.exists():
        idd_files = list(idd_dir.glob("*Energy+.idd*"))
        if idd_files:
            return idd_files[0]

    return None
