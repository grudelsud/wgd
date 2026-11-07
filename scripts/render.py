# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""Render everything generated from the vault's .wgd/schema.yaml. Safe to re-run.

    render.py VAULT

Writes templates/<type>.md and views/Everything.base, creates type folders, and refreshes
the generated blocks in CONTRIBUTING.md and CLAUDE.md (other content in those files is kept).
"""

import json
import re
import sys
from pathlib import Path

import yaml

from wgdlib import DEFAULTS, check_schema, fields_for, load_schema, load_yaml

BASE_FOLDERS = ["inbox", "attachments", "templates", "views"]
VIEWS_FILE = "views/Everything.base"
CONTRIB_START, CONTRIB_END = "<!-- wgd:schema:start -->", "<!-- wgd:schema:end -->"
CLAUDE_START_RE, CLAUDE_END = r"<!-- wgd:start[^>]*-->", "<!-- wgd:end -->"


def template_value(name, spec, type_name, tspec):
    if name == "type":
        return type_name
    if name == "layer" and tspec.get("default_layer"):
        return tspec["default_layer"]
    if "default" in spec:
        return spec["default"]
    kind = spec.get("kind")
    if kind in ("list", "links"):
        return []
    if kind == "date" and spec.get("required"):
        return '"{{date:YYYY-MM-DD}}"'
    if kind == "datetime":
        return '"{{date:YYYY-MM-DDTHH:mm}}"'
    return None


def render_template(schema, type_name):
    tspec = schema["types"][type_name] or {}
    lines = ["---"]
    for name, spec in fields_for(schema, type_name).items():
        if name == "source_ref":
            continue
        value = template_value(name, spec, type_name, tspec)
        if value is None:
            lines.append(f"{name}:")
        elif value == []:
            lines.append(f"{name}: []")
        else:
            lines.append(f"{name}: {value}")
    lines.append("---")
    body = (tspec.get("body") or "").strip()
    return "\n".join(lines) + "\n\n# {{title}}\n" + (f"\n{body}\n" if body else "")


def describe(spec):
    parts = []
    if spec.get("values"):
        parts.append(" \\| ".join(f"`{v}`" for v in spec["values"]))
    if spec.get("target"):
        parts.append(f"links to `{spec['target']}` notes")
    if spec.get("ongoing"):
        parts.append('or `ongoing`')
    if spec.get("default") is not None:
        parts.append(f"default `{spec['default']}`")
    if spec.get("required_if"):
        parts.append("required when " + ", ".join(f"{k} is {v}" for k, v in spec["required_if"].items()))
    if spec.get("description"):
        parts.append(spec["description"].replace("|", "\\|"))
    return "; ".join(parts)


def field_rows(fields):
    rows = ["| field | kind | required | notes |", "|---|---|---|---|"]
    for name, spec in fields.items():
        rows.append(f"| `{name}` | {spec.get('kind', '')} | {'yes' if spec.get('required') else ''} | {describe(spec)} |")
    return rows


def render_contributing_block(schema):
    common = schema.get("common") or {}
    out = [
        f"## Schema (version {schema.get('version', 1)})",
        "",
        "### Types",
        "",
        "| type | folder | default layer | description |",
        "|---|---|---|---|",
    ]
    for type_name, tspec in schema["types"].items():
        tspec = tspec or {}
        out.append(f"| `{type_name}` | `{tspec.get('folder', '')}/` | {tspec.get('default_layer', '')} | {tspec.get('description', '')} |")
    out += ["", "Template for each type: `templates/<type>.md`.", "", "### Fields on every type", ""]
    common_fields = fields_for({**schema, "types": {"_": {}}}, "_")
    common_fields["type"]["values"] = list(schema["types"])
    out += field_rows(common_fields)
    for type_name, tspec in schema["types"].items():
        extra = (tspec or {}).get("fields") or {}
        if extra:
            merged = fields_for(schema, type_name)
            out += ["", f"### Specific to `{type_name}`", ""] + field_rows({k: merged[k] for k in extra})
    excluded = ", ".join(f"`{e}`" for e in schema.get("exclude") or [])
    out += ["", f"Not wgd content (never validated or moved): {excluded}, and any dot-folder.", ""]
    return "\n".join(out)


def render_claude_block(schema):
    types = ", ".join(f"`{t}`" for t in schema["types"])
    return f"""<!-- wgd:start schema={schema.get('version', 1)} -->
## wgd

This vault is managed by wgd, a Claude Code plugin. Content types ({types}) and their fields are defined in `.wgd/schema.yaml`; the rules are in `CONTRIBUTING.md`. Follow them for any note you create, edit or move.

- Use `/wgd:capture` to add content, `/wgd:ask` to query it, `/wgd:add-type` to add a content type, `/wgd:discover` to propose types from existing content, `/wgd:backfill` to bring existing notes in line, `/wgd:tidy` to file attachments and clean up folders, `/wgd:init` to re-render after editing the schema.
- `templates/`, `views/Everything.base`, the generated block in `CONTRIBUTING.md` and this section are generated: change the schema instead. Other files in `views/` are yours and wgd leaves them alone.
- Validate after every write, then commit. Never read or write the body of a note with `visibility: sealed`.
{CLAUDE_END}"""


def _q(expr):
    """Single-quote a Bases filter expression for YAML."""
    return "'" + expr.replace("'", "''") + "'"


def _table_view(name, filters, order, direction, group_by=None):
    lines = ["  - type: table", f"    name: {name}"]
    if filters:
        lines += ["    filters:", "      and:"] + [f"        - {_q(f)}" for f in filters]
    if group_by:
        lines += ["    groupBy:", f"      property: {group_by}", "      direction: ASC"]
    lines += ["    order:"] + [f"      - {col}" for col in order]
    return lines + ["    sort:", "      - property: start", f"        direction: {direction}"]


def render_base(schema):
    """An Obsidian Base over all wgd notes: a timeline, what is ongoing, and one view per type, grouped by layer."""
    common = list(schema.get("common") or {})
    trailing = [c for c in ("layer", "contexts", "people", "tags") if c in common]
    group_by = "layer" if "layer" in common else None
    folders = [e.strip("/") for e in schema.get("exclude") or [] if not e.endswith(".md")]
    lines = [
        "# Generated by wgd from .wgd/schema.yaml and rewritten when the schema changes.",
        "# To customise, duplicate this file inside views/ and edit the copy.",
        "filters:",
        "  and:",
        "    - " + _q('file.ext == "md"'),
        "    - " + _q('file.hasProperty("type")'),
    ]
    if folders:
        lines += ["    - not:"] + ["        - " + _q(f'file.inFolder("{f}")') for f in folders]
    lines.append("views:")
    lines += _table_view("Timeline", [], ["file.name", "type", "start", "end"] + trailing, "DESC", group_by)
    lines += _table_view("Ongoing", ['end == "ongoing"'], ["file.name", "type", "start"] + trailing, "ASC", group_by)
    for type_name, tspec in schema["types"].items():
        extra = [f for f in ((tspec or {}).get("fields") or {}) if f not in common]
        name = type_name.replace("-", " ").capitalize()
        order = ["file.name", "start", "end"] + extra + trailing
        lines += _table_view(name, [f'type == "{type_name}"'], order, "DESC", group_by)
    return "\n".join(lines) + "\n"


def replace_block(text, start_re, end, block):
    m = re.search(start_re + r".*?" + re.escape(end), text, flags=re.S)
    if m:
        return text[:m.start()] + block + text[m.end():]
    return text.rstrip() + ("\n\n" if text.strip() else "") + block + "\n"


def write_if_changed(path, content, changed):
    if not path.exists() or path.read_text() != content:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        changed.append(path)


def render(vault):
    vault = Path(vault)
    schema = load_schema(vault)
    errors = check_schema(schema)
    if errors:
        raise SystemExit("schema errors:\n" + "\n".join(errors))
    changed = []

    for folder in BASE_FOLDERS + [(t or {}).get("folder", "").split("{")[0] for t in schema["types"].values()]:
        folder = folder.strip("/")
        if folder and not (vault / folder).is_dir():
            (vault / folder).mkdir(parents=True)
            changed.append(vault / folder)

    for type_name in schema["types"]:
        write_if_changed(vault / "templates" / f"{type_name}.md", render_template(schema, type_name), changed)

    # Obsidian reformats .base files when it opens them, so only rewrite when the meaning changed
    base, wanted = vault / VIEWS_FILE, render_base(schema)
    try:
        same = base.exists() and load_yaml(base.read_text()) == load_yaml(wanted)
    except yaml.YAMLError:
        same = False
    if not same:
        write_if_changed(base, wanted, changed)

    contrib = vault / "CONTRIBUTING.md"
    text = contrib.read_text() if contrib.exists() else (DEFAULTS / "CONTRIBUTING.md").read_text()
    if CONTRIB_START not in text:
        text = text.rstrip() + "\n\n" + CONTRIB_START + "\n" + CONTRIB_END + "\n"
    block = f"{CONTRIB_START}\n{render_contributing_block(schema)}\n{CONTRIB_END}"
    write_if_changed(contrib, replace_block(text, re.escape(CONTRIB_START), CONTRIB_END, block), changed)

    claude = vault / "CLAUDE.md"
    text = claude.read_text() if claude.exists() else ""
    write_if_changed(claude, replace_block(text, CLAUDE_START_RE, CLAUDE_END, render_claude_block(schema)), changed)

    return [p.relative_to(vault).as_posix() for p in changed]


def merge_obsidian(vault):
    """Merge wgd's Obsidian settings into .obsidian/*.json, keeping every other key."""
    vault = Path(vault)
    changed = []
    for src in sorted((DEFAULTS / "obsidian").glob("*.json")):
        dest = vault / ".obsidian" / src.name
        current = json.loads(dest.read_text()) if dest.exists() else None
        wanted = json.loads(src.read_text())
        if src.name == "core-plugins.json" and isinstance(current, list):
            merged = current + [k for k, on in wanted.items() if on and k not in current]
        else:
            merged = {**(current or {}), **wanted}
        write_if_changed(dest, json.dumps(merged, indent=2) + "\n", changed)
    return [p.relative_to(vault).as_posix() for p in changed]


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    for path in render(sys.argv[1]):
        print(f"updated {path}")
