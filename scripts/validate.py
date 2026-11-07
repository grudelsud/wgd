# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""Validate vault notes against the vault's own .wgd/schema.yaml.

    validate.py VAULT [FILE ...]   check the given files, or every note; exit 1 on problems
    validate.py VAULT --summary    counts only, always exit 0 (used by /wgd:init on existing vaults)
    validate.py VAULT --schema     check the schema itself
"""

import argparse
import sys
from pathlib import Path

from wgdlib import Index, check_schema, iter_notes, load_schema, validate_note


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vault")
    ap.add_argument("files", nargs="*")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--schema", action="store_true")
    args = ap.parse_args()

    vault = Path(args.vault).resolve()
    schema = load_schema(vault)
    schema_errors = check_schema(schema)
    for e in schema_errors:
        print(f".wgd/schema.yaml: {e}")
    if args.schema or schema_errors:
        return 1 if schema_errors else 0

    if args.files:
        rels = [Path(f).resolve().relative_to(vault).as_posix() for f in args.files]
    else:
        rels = list(iter_notes(vault, schema))
    index = Index(vault)
    counts = {"conforming": 0, "not wgd content": 0, "invalid": 0}
    failed = False
    for rel in rels:
        errors = validate_note(vault, schema, rel, index)
        if not errors:
            counts["conforming"] += 1
            continue
        failed = True
        counts["not wgd content" if errors[0].startswith("not wgd content") else "invalid"] += 1
        if not args.summary:
            for e in errors:
                print(f"{rel}: {e}")
    if args.summary:
        print(f"{len(rels)} notes: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
        return 0
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
