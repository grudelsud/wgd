# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""Inventory notes for /wgd:backfill: the facts needed to infer frontmatter and plan moves.

    inventory.py VAULT [SUBPATH] [--all]

Writes .wgd/cache/inventory.json and prints a short report. File birth times are
recorded on the first run and kept on later runs, so moves cannot lose them.
Only non-conforming notes are listed unless --all is given.
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from wgdlib import Index, iter_notes, load_schema, split_frontmatter, validate_note

FILENAME_DATE_RE = re.compile(r"(?<!\d)(\d{4})[-_.]?(\d{2})(?:[-_.]?(\d{2}))?(?!\d)")
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)")


def filename_date(stem):
    m = FILENAME_DATE_RE.search(stem)
    if not m:
        return None
    y, mo, d = m.groups()
    if not (1900 <= int(y) <= 2100 and 1 <= int(mo) <= 12) or (d and not 1 <= int(d) <= 31):
        return None
    return f"{y}-{mo}" + (f"-{d}" if d else "")


def iso(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%dT%H:%M")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vault")
    ap.add_argument("subpath", nargs="?")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    vault = Path(args.vault).resolve()
    schema = load_schema(vault)
    out = vault / ".wgd/cache/inventory.json"
    previous = json.loads(out.read_text()) if out.exists() else {}
    known_birth = {n["path"]: n["birthtime"] for n in previous.get("notes", [])}
    index = Index(vault)

    notes = []
    for rel in iter_notes(vault, schema, args.subpath):
        path = vault / rel
        text = path.read_text(errors="replace")
        fm, body = split_frontmatter(text)
        errors = validate_note(vault, schema, rel, index, fm)
        if errors == [] and not args.all:
            continue
        st = path.stat()
        notes.append({
            "path": rel,
            "birthtime": known_birth.get(rel) or iso(getattr(st, "st_birthtime", st.st_mtime)),
            "mtime": iso(st.st_mtime),
            "filename_date": filename_date(path.stem),
            "frontmatter": fm or {},
            "errors": errors,
            "words": len(body.split()),
        })

    path_links = {}
    for rel in iter_notes(vault, schema):
        for target in WIKILINK_RE.findall((vault / rel).read_text(errors="replace")):
            if "/" in target:
                path_links.setdefault(rel, []).append(target.strip())
    duplicates = {stem: paths for stem, paths in index.by_stem.items() if len(paths) > 1}

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"notes": notes, "duplicate_names": duplicates, "path_links": path_links},
                              indent=1, ensure_ascii=False, default=str))
    no_type = sum(1 for n in notes if n["errors"][:1] == ["not wgd content (no frontmatter type)"])
    print(f"{len(notes)} notes to backfill ({no_type} without wgd frontmatter, {len(notes) - no_type} invalid)")
    print(f"{len(duplicates)} duplicate note names, {len(path_links)} notes with path-qualified links")
    print(f"written to {out.relative_to(vault)}")


if __name__ == "__main__":
    main()
