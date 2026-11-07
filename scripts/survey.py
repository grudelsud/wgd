# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""Survey a vault's content for /wgd:discover: the signals that suggest content types.

    survey.py VAULT [SUBPATH] [--top N]

Read-only. Prints a report of folders, frontmatter keys and values, tags, recurring
headings, most-linked targets, filename dates, sample paths and non-markdown files.
"""

import argparse
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

from inventory import WIKILINK_RE, filename_date
from wgdlib import Index, as_str, iter_notes, load_schema, split_frontmatter

TAG_RE = re.compile(r"(?<![\w&/])#([A-Za-z][\w/-]*)")
HEADING_RE = re.compile(r"^#{2,3}\s+(.+?)\s*#*$", re.M)
MAX_VALUES = 20   # report a key's values only when it has at most this many distinct ones


def survey(vault, subpath=None, top=30):
    vault = Path(vault)
    schema = load_schema(vault)
    index = Index(vault)
    folders, folder_samples = Counter(), defaultdict(list)
    keys, values = Counter(), defaultdict(Counter)
    tags, headings, links = Counter(), Counter(), Counter()
    dated, typed, words = 0, Counter(), 0
    notes = list(iter_notes(vault, schema, subpath))

    for rel in notes:
        text = (vault / rel).read_text(errors="replace")
        fm, body = split_frontmatter(text)
        fm = fm or {}
        folder = Path(rel).parent.as_posix()
        folders[folder] += 1
        folder_samples[folder].append(rel)
        words += len(body.split())
        dated += filename_date(Path(rel).stem) is not None
        if fm.get("type") in schema["types"]:
            typed[fm["type"]] += 1
        for key, value in fm.items():
            keys[key] += 1
            for v in value if isinstance(value, list) else [value]:
                if v is not None and not isinstance(v, (dict, list)):
                    values[key][as_str(v)] += 1
        fm_tags = fm.get("tags")
        for t in fm_tags if isinstance(fm_tags, list) else [fm_tags]:
            if t:
                tags[str(t).lstrip("#")] += 1
        tags.update(set(TAG_RE.findall(body)))
        headings.update({h.strip().lower() for h in HEADING_RE.findall(body)})
        links.update({t.strip().split("/")[-1].removesuffix(".md") for t in WIKILINK_RE.findall(text)})

    other = Counter()
    for dirpath, dirnames, filenames in os.walk(vault / subpath if subpath else vault):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fn in filenames:
            if not fn.endswith(".md") and not fn.startswith("."):
                other[Path(fn).suffix.lower() or "(none)"] += 1

    out = [f"# Survey of {vault.name}{'/' + subpath if subpath else ''}", "",
           f"{len(notes)} notes, {words} words; {dated} with a date in the filename; "
           f"already typed: {', '.join(f'{t} {n}' for t, n in typed.items()) or 'none'}", ""]

    out += ["## Folders (notes, samples)", ""]
    for folder, n in folders.most_common(top):
        s = folder_samples[folder]
        picks = list(dict.fromkeys([s[0], s[len(s) // 2], s[-1]]))
        out.append(f"- {folder}/ — {n}: " + "; ".join(Path(p).name for p in picks))

    out += ["", "## Frontmatter keys (notes using them, values when few)", ""]
    for key, n in keys.most_common(top):
        vals = values[key]
        shown = ", ".join(f"{v} ({c})" for v, c in vals.most_common(8)) if 0 < len(vals) <= MAX_VALUES else ""
        out.append(f"- {key} — {n}" + (f": {shown}" if shown else ""))

    def section(title, counter, min_count=2):
        rows = [f"- {k} — {n}" for k, n in counter.most_common(top) if n >= min_count]
        return ["", f"## {title}", ""] + (rows or ["- none"])

    out += section("Tags (frontmatter and inline)", tags)
    out += section("Recurring headings (h2/h3, notes using them)", headings, 3)
    linked = Counter({k: n for k, n in links.items() if n >= 2})
    out += ["", "## Most linked targets (notes linking; * = no such note)", ""]
    out += [f"- {k}{'' if index.resolve(k) else ' *'} — {n}" for k, n in linked.most_common(top)] or ["- none"]
    out += section("Non-markdown files by extension", other, 1)
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vault")
    ap.add_argument("subpath", nargs="?")
    ap.add_argument("--top", type=int, default=30)
    args = ap.parse_args()
    print(survey(Path(args.vault).resolve(), args.subpath, args.top), end="")


if __name__ == "__main__":
    main()
