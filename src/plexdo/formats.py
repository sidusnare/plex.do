# SPDX-License-Identifier: GPL-3.0-or-later

"""Serialisers for the machine-readable output formats.

Every renderer accepts either a list of records or a single record, so that a
command emitting one object (``show-metadata``, ``login``) and a command
emitting many (``list-titles``) can share one code path.
"""

from typing import Any, Dict, List, Union
from xml.sax.saxutils import escape, quoteattr
import csv
import io
import json



Record = Dict[str, Any]
Payload = Union[Record, List[Record], Any]

# "table" is handled by console.print_table / print_metadata, not here.
OUTPUT_FORMATS = ("table", "json", "yaml", "csv", "clixml")
MACHINE_FORMATS = ("json", "yaml", "csv", "clixml")


def _as_records(data: Payload) -> List[Record]:
    """Normalise a payload to a list of records."""
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def _scalar(value: Any) -> Any:
    """Reduce a value to something the serialisers can represent."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def to_json(data: Payload) -> str:
    """Render as JSON. Non-ASCII is escaped, so any console can print it."""
    return json.dumps(data, default=str)


def _yaml_scalar(value: Any) -> str:
    """Render one YAML scalar.

    Strings are always double-quoted. That is more verbose than plain style
    but is unconditionally valid, sidestepping the YAML type-guessing that
    would otherwise turn a title like "NO" or "1.10" into a bool or a float.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    text = text.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return f'"{text}"'


def to_yaml(data: Payload) -> str:
    """Render as a YAML sequence of mappings, or a single mapping."""
    if isinstance(data, dict):
        return "\n".join(f"{key}: {_yaml_scalar(val)}" for key, val in data.items())
    records = _as_records(data)
    if not records:
        return "[]"
    lines: List[str] = []
    for record in records:
        first = True
        for key, val in record.items():
            prefix = "- " if first else "  "
            lines.append(f"{prefix}{key}: {_yaml_scalar(val)}")
            first = False
    return "\n".join(lines)


def to_csv(data: Payload) -> str:
    """Render as CSV with a header row.

    Uses "\\n" line endings rather than the RFC's CRLF so the output matches
    every other format when piped into ordinary Unix tooling.
    """
    records = _as_records(data)
    if not records:
        return ""
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer, fieldnames=list(records[0].keys()),
        extrasaction="ignore", lineterminator="\n",
    )
    writer.writeheader()
    for record in records:
        writer.writerow({key: _scalar(val) for key, val in record.items()})
    return buffer.getvalue().rstrip("\n")


def _clixml_property(name: str, value: Any) -> str:
    """Render one typed CLIXML property element."""
    attr = quoteattr(name)
    if value is None:
        return f"<Nil N={attr} />"
    if isinstance(value, bool):
        return f"<B N={attr}>{'true' if value else 'false'}</B>"
    if isinstance(value, int):
        return f"<I32 N={attr}>{value}</I32>"
    if isinstance(value, float):
        return f"<Db N={attr}>{value}</Db>"
    return f"<S N={attr}>{escape(str(value))}</S>"


def to_clixml(data: Payload) -> str:
    """Render as PowerShell CLIXML, readable by Import-Clixml.

    The first object carries the type names and later objects reference them
    by RefId, which is what ConvertTo-Clixml itself emits.
    """
    records = _as_records(data)
    lines = [
        '<Objs Version="1.1.0.1" '
        'xmlns="http://schemas.microsoft.com/powershell/2004/04">'
    ]
    for index, record in enumerate(records):
        lines.append(f'  <Obj RefId="{index}">')
        if index == 0:
            lines.append('    <TN RefId="0">')
            lines.append("      <T>System.Management.Automation.PSCustomObject</T>")
            lines.append("      <T>System.Object</T>")
            lines.append("    </TN>")
        else:
            lines.append('    <TNRef RefId="0" />')
        lines.append("    <MS>")
        for key, value in record.items():
            lines.append("      " + _clixml_property(key, _scalar(value)))
        lines.append("    </MS>")
        lines.append("  </Obj>")
    lines.append("</Objs>")
    return "\n".join(lines)


_RENDERERS = {
    "json": to_json,
    "yaml": to_yaml,
    "csv": to_csv,
    "clixml": to_clixml,
}


def render(data: Payload, output_fmt: str) -> str:
    """Render a payload in the named machine-readable format."""
    try:
        return _RENDERERS[output_fmt](data)
    except KeyError:
        raise ValueError(f"Unknown output format: {output_fmt!r}") from None
