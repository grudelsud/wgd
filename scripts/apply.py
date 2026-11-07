# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""Apply an approved backfill batch: merge frontmatter, move notes to their type folder, fix links.

    apply.py VAULT PLAN.json [--dry-run]

PLAN.json is a list of {"path": "old/Note.md", "frontmatter": {...}, "to": "optional/new/path.md"}.
Frontmatter keys are merged over the existing ones (a null value removes the key); the body is
never touched. Without "to", the note moves to its type's folder and keeps its filename.
Path-qualified links to moved notes ([[old/dir/Note]]) are rewritten; shortest links need nothing.
Moves use `git mv` for tracked files. Does not commit. Exit 1 if any note fails validation.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from wgdlib import Index, dump_frontmatter, expected_folder, iter_notes, load_schema, split_frontmatter, validate_note


def destination(schema, rel, fm, to):
    if to:
        return to
    folder = expected_folder(schema, fm)
    if folder is None:
        return rel
    return f"{folder}/{Path(rel).name}" if folder else Path(rel).name


def is_tracked(vault, rel):
    return subprocess.run(["git", "ls-files", "--error-unmatch", rel], cwd=vault,
                          capture_output=True).returncode == 0


def move(vault, src, dest):
    (vault / dest).parent.mkdir(parents=True, exist_ok=True)
    if is_tracked(vault, src):
        subprocess.run(["git", "mv", src, dest], cwd=vault, check=True)
    else:
        (vault / src).rename(vault / dest)


def rewrite_links(vault, schema, moves):
    """Rewrite [[old/path]] links (with or without .md) to the new path. Returns changed files."""
    if not moves:
        return []
    patterns = [(re.compile(r"\[\[" + re.escape(old[:-3]) + r"(\.md)?(?=[\]|#])"), "[[" + new[:-3])
                for old, new in moves.items()]
    changed = []
    for rel in iter_notes(vault, schema):
        path = vault / rel
        text = path.read_text()
        new_text = text
        for pattern, repl in patterns:
            new_text = pattern.sub(repl, new_text)
        if new_text != text:
            path.write_text(new_text)
            changed.append(rel)
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vault")
    ap.add_argument("plan")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    vault = Path(args.vault).resolve()
    schema = load_schema(vault)
    plan = json.loads(Path(args.plan).read_text())

    moves, written, problems = {}, [], False
    for item in plan:
        rel = item["path"]
        path = vault / rel
        if not path.exists():
            print(f"{rel}: missing, skipped")
            problems = True
            continue
        text = path.read_text()
        fm, body = split_frontmatter(text)
        merged = {**(fm or {}), **item.get("frontmatter", {})}
        merged = {k: v for k, v in merged.items() if v is not None}
        dest = destination(schema, rel, merged, item.get("to"))
        if dest != rel and ((vault / dest).exists() or dest in moves.values()):
            print(f"{rel}: {dest} already exists, skipped")
            problems = True
            continue
        print(f"{rel} -> {dest}" if dest != rel else f"{rel} (stays)")
        if args.dry_run:
            continue
        path.write_text(dump_frontmatter(merged, schema) + body)
        if dest != rel:
            move(vault, rel, dest)
            moves[rel] = dest
        written.append(dest)

    if args.dry_run:
        return 1 if problems else 0
    for rel in rewrite_links(vault, schema, moves):
        print(f"rewrote links in {rel}")
    index = Index(vault)
    for rel in written:
        for e in validate_note(vault, schema, rel, index):
            print(f"{rel}: {e}")
            problems = True
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
