"""Shared helpers for the wgd scripts: schema, frontmatter, vault walking, validation."""

import os
import re
from pathlib import Path

import yaml

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
DEFAULTS = PLUGIN_ROOT / "defaults"
SCHEMA_PATH = ".wgd/schema.yaml"

DATE_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2}(T\d{2}:\d{2}(:\d{2})?)?)?)?$")
DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$")
LINK_RE = re.compile(r"^\[\[([^\]|#]+)(#[^\]|]*)?(\|[^\]]*)?\]\]$")
KINDS = {"date", "datetime", "text", "url", "bool", "enum", "list", "links"}


class _StrLoader(yaml.SafeLoader):
    """SafeLoader that keeps dates as strings, the way Obsidian stores them."""


_StrLoader.yaml_implicit_resolvers = {
    ch: [r for r in resolvers if r[0] != "tag:yaml.org,2002:timestamp"]
    for ch, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def load_yaml(text):
    return yaml.load(text, Loader=_StrLoader)


def load_schema(vault):
    path = Path(vault) / SCHEMA_PATH
    if not path.exists():
        raise SystemExit(f"no wgd schema at {path}; run /wgd:init first")
    return load_yaml(path.read_text())


def fields_for(schema, type_name):
    """Common fields merged with the type's additions and overrides, in a stable order."""
    fields = {name: dict(spec or {}) for name, spec in (schema.get("common") or {}).items()}
    for name, spec in ((schema["types"][type_name] or {}).get("fields") or {}).items():
        fields[name] = {**fields.get(name, {}), **(spec or {})}
    if "type" in fields:
        fields["type"]["values"] = list(schema["types"])
    return fields


def check_schema(schema):
    errors = []
    if not isinstance(schema, dict) or not isinstance(schema.get("types"), dict) or not schema["types"]:
        return ["schema: needs a non-empty `types` mapping"]
    for type_name, tspec in schema["types"].items():
        if not re.fullmatch(r"[a-z][a-z0-9-]*", str(type_name)):
            errors.append(f"type {type_name}: name must be lowercase kebab-case")
        if not (tspec or {}).get("folder"):
            errors.append(f"type {type_name}: missing folder")
        for name, spec in fields_for(schema, type_name).items():
            kind = spec.get("kind")
            if kind not in KINDS:
                errors.append(f"type {type_name}, field {name}: unknown kind {kind!r}")
            if kind == "enum" and name != "type" and not spec.get("values"):
                errors.append(f"type {type_name}, field {name}: enum needs values")
            if kind == "links" and spec.get("target") and spec["target"] not in schema["types"]:
                errors.append(f"type {type_name}, field {name}: target {spec['target']!r} is not a type")
    return errors


def split_frontmatter(text):
    """Return (frontmatter dict or None, body)."""
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---", 3)
    if end == -1:
        return None, text
    close = text.find("\n", end + 4)
    body = "" if close == -1 else text[close + 1:]
    try:
        fm = load_yaml(text[4:end + 1])
    except yaml.YAMLError:
        return None, text
    return (fm if isinstance(fm, dict) else {}), body


def dump_frontmatter(fm, schema=None):
    order = []
    if schema:
        order = list(fields_for(schema, fm["type"])) if fm.get("type") in schema["types"] else list(schema.get("common") or {})
    keys = [k for k in order if k in fm] + [k for k in fm if k not in order]
    text = yaml.safe_dump({k: fm[k] for k in keys}, sort_keys=False, allow_unicode=True, default_flow_style=False, width=1000)
    return f"---\n{text}---\n"


def is_excluded(rel, schema):
    parts = Path(rel).parts
    if any(p.startswith(".") for p in parts):
        return True
    for ex in schema.get("exclude") or []:
        ex = ex.strip("/")
        if rel == ex or rel.startswith(ex + "/"):
            return True
    return False


def iter_notes(vault, schema, under=None):
    vault = Path(vault)
    root = vault / under if under else vault
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for fn in sorted(filenames):
            if fn.endswith(".md"):
                rel = (Path(dirpath) / fn).relative_to(vault).as_posix()
                if not is_excluded(rel, schema):
                    yield rel


class Index:
    """Every .md file in the vault, for resolving [[links]] the way Obsidian does."""

    def __init__(self, vault):
        self.root = Path(vault)
        self.by_stem, self.by_path = {}, {}
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for fn in filenames:
                if fn.endswith(".md"):
                    rel = (Path(dirpath) / fn).relative_to(self.root).as_posix()
                    self.by_stem.setdefault(fn[:-3], []).append(rel)
                    self.by_path[rel[:-3]] = rel

    def resolve(self, target):
        target = target.strip()
        if target.endswith(".md"):
            target = target[:-3]
        if "/" in target:
            return [self.by_path[target]] if target in self.by_path else []
        return self.by_stem.get(target, [])


def as_str(value):
    return None if value is None else str(value)


def expected_folder(schema, fm):
    tspec = schema["types"].get(fm.get("type")) or {}
    pattern = tspec.get("folder", "")
    if "{" not in pattern:
        return pattern.strip("/")
    start = as_str(fm.get("start")) or ""
    if not DATE_RE.match(start):
        return None
    yyyy, mm = start[:4], start[5:7] or "00"
    return pattern.replace("{yyyy}", yyyy).replace("{mm}", mm).strip("/")


def _empty(value):
    return value is None or value == "" or value == []


def validate_note(vault, schema, rel, index=None, fm=None):
    """Return a list of problems with one note; empty means it conforms."""
    if fm is None:
        fm, _ = split_frontmatter((Path(vault) / rel).read_text(errors="replace"))
    if not fm or "type" not in fm:
        return ["not wgd content (no frontmatter type)"]
    type_name = fm["type"]
    if type_name not in schema["types"]:
        return [f"type {type_name!r} is not in the schema ({', '.join(schema['types'])})"]
    index = index or Index(vault)
    errors = []
    for name, spec in fields_for(schema, type_name).items():
        value = fm.get(name)
        required = spec.get("required", False)
        cond = spec.get("required_if") or {}
        if cond and all(as_str(fm.get(k)) == as_str(v) for k, v in cond.items()):
            required = True
        if _empty(value):
            if required:
                errors.append(f"{name}: required")
            continue
        errors += [f"{name}: {e}" for e in _check_value(spec, value, schema, index)]
    start, end = as_str(fm.get("start")), as_str(fm.get("end"))
    if start and end and end != "ongoing" and DATE_RE.match(start) and DATE_RE.match(end):
        n = min(len(start), len(end))
        if end[:n] < start[:n]:
            errors.append("end: before start")
    folder = expected_folder(schema, fm)
    actual = Path(rel).parent.as_posix()
    if folder is not None and actual != (folder or "."):
        errors.append(f"location: expected in {folder or 'vault root'}/, found in {actual}/")
    return errors


def _check_value(spec, value, schema, index):
    kind = spec.get("kind")
    s = as_str(value)
    if kind == "date":
        if spec.get("ongoing") and s == "ongoing":
            return []
        return [] if DATE_RE.match(s) else [f"{s!r} is not a partial ISO date (2024, 2024-03, 2024-03-12, 2024-03-12T10:00)"]
    if kind == "datetime":
        return [] if DATETIME_RE.match(s) else [f"{s!r} is not a datetime (2024-03-12T10:00)"]
    if kind == "bool":
        return [] if isinstance(value, bool) else [f"{s!r} is not true/false"]
    if kind == "enum":
        if s == "sealed" and "sealed" not in spec["values"]:
            return ["sealed (encrypted) notes are not supported yet"]
        return [] if s in [as_str(v) for v in spec["values"]] else [f"{s!r} is not one of {', '.join(map(str, spec['values']))}"]
    if kind == "url":
        return [] if re.match(r"^[a-z][a-z0-9+.-]*://", s) else [f"{s!r} is not a URL"]
    if kind in ("text",):
        return [] if not isinstance(value, (list, dict)) else ["must be a single value"]
    if kind == "list":
        return [] if isinstance(value, list) else ["must be a list"]
    if kind == "links":
        if not isinstance(value, list):
            return ['must be a list of quoted links, e.g. ["[[Name]]"]']
        errors = []
        for item in value:
            m = LINK_RE.match(as_str(item) or "")
            if not m:
                errors.append(f"{item!r} is not a [[link]]")
                continue
            hits = index.resolve(m.group(1))
            if not hits:
                errors.append(f"{item} does not resolve to a note")
            elif len(hits) > 1:
                errors.append(f"{item} is ambiguous ({', '.join(hits)})")
            elif spec.get("target"):
                target_fm, _ = split_frontmatter((index.root / hits[0]).read_text(errors="replace"))
                if target_fm and target_fm.get("type") not in (None, spec["target"]):
                    errors.append(f"{item} is a {target_fm.get('type')}, expected a {spec['target']}")
        return errors
    return []

