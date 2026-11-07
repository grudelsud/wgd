# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""Install wgd into a vault. Never moves or edits notes; safe to re-run.

    init.py VAULT [--obsidian]

Copies the default schema if the vault has none (an existing schema is kept), renders
templates, folders, CONTRIBUTING.md and CLAUDE.md, and with --obsidian merges wgd's
settings into .obsidian/ (attachments folder, new notes in inbox/, templates, core plugins).
Adds Obsidian's volatile files to .gitignore; running git is left to the caller.
"""

import argparse
import shutil
from pathlib import Path

from render import merge_obsidian, render
from wgdlib import DEFAULTS, SCHEMA_PATH

GITIGNORE = [".obsidian/workspace*", ".trash/"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vault")
    ap.add_argument("--obsidian", action="store_true")
    args = ap.parse_args()
    vault = Path(args.vault).resolve()
    if not vault.is_dir():
        raise SystemExit(f"{vault} is not a directory")

    schema = vault / SCHEMA_PATH
    if schema.exists():
        print(f"kept {SCHEMA_PATH}")
    else:
        schema.parent.mkdir(exist_ok=True)
        shutil.copy(DEFAULTS / "schema.yaml", schema)
        print(f"created {SCHEMA_PATH}")
    ignore = vault / ".wgd/.gitignore"
    if not ignore.exists():
        ignore.write_text("cache/\n")
    gitignore = vault / ".gitignore"
    existing = gitignore.read_text().splitlines() if gitignore.exists() else []
    missing = [line for line in GITIGNORE if line not in existing]
    if missing:
        gitignore.write_text("\n".join(existing + missing) + "\n")
        print("updated .gitignore")

    for path in render(vault):
        print(f"updated {path}")
    if args.obsidian:
        for path in merge_obsidian(vault):
            print(f"updated {path}")


if __name__ == "__main__":
    main()
