# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""Find notes by frontmatter, links, text and time overlap. Read-only. Used by /wgd:ask.

    query.py VAULT [--type T] [--layer L] [--link NAME] [--text WORDS]
                   [--from DATE] [--to DATE] [--overlaps NOTE.md] [--limit N]

Filters combine with AND. --link matches [[NAME]] in frontmatter or body. --from/--to
keep notes whose span overlaps the range; --overlaps uses another note's span as the range.
Dates are partial ISO (2019, 2019-03, ...): "2019" covers the whole year. Output is one
line per note, ordered by start: "start..end  type  layer  path". Sealed notes are matched
on frontmatter only.
"""

import argparse
import re
from pathlib import Path

from wgdlib import DATE_RE, as_str, iter_notes, load_schema, split_frontmatter

LOW, HIGH = "0000-01-01T00:00", "9999-12-31T23:59"


def bound(date, upper):
    """Pad a partial date to the lowest or highest moment it can mean."""
    pad = "9999-12-31T23:59" if upper else "0000-01-01T00:00"
    return date + pad[len(date):] if date else (HIGH if upper else LOW)


def span(fm):
    start, end = as_str(fm.get("start")), as_str(fm.get("end"))
    if not start or not DATE_RE.match(start):
        return None
    if end == "ongoing":
        return bound(start, False), HIGH
    if end and DATE_RE.match(end):
        return bound(start, False), bound(end, True)
    return bound(start, False), bound(start, True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vault")
    ap.add_argument("--type")
    ap.add_argument("--layer")
    ap.add_argument("--link", action="append", default=[])
    ap.add_argument("--text")
    ap.add_argument("--from", dest="date_from")
    ap.add_argument("--to", dest="date_to")
    ap.add_argument("--overlaps")
    ap.add_argument("--limit", type=int, default=100)
    args = ap.parse_args()

    vault = Path(args.vault).resolve()
    schema = load_schema(vault)
    lo, hi = (bound(args.date_from, False) if args.date_from else None), (bound(args.date_to, True) if args.date_to else None)
    if args.overlaps:
        fm, _ = split_frontmatter((vault / args.overlaps).read_text())
        lo, hi = span(fm or {}) or (None, None)
        if lo is None:
            raise SystemExit(f"{args.overlaps} has no usable start date")

    rows = []
    for rel in iter_notes(vault, schema):
        text = (vault / rel).read_text(errors="replace")
        fm, body = split_frontmatter(text)
        fm = fm or {}
        if fm.get("visibility") == "sealed":
            text = text[: len(text) - len(body)]
        if args.type and fm.get("type") != args.type:
            continue
        if args.layer and fm.get("layer") != args.layer:
            continue
        if any(not re.search(r"\[\[" + re.escape(name) + r"(\.md)?[\]|#]", text) for name in args.link):
            continue
        if args.text and not all(w.lower() in (rel + " " + text).lower() for w in args.text.split()):
            continue
        s = span(fm)
        if (lo or hi) and (not s or (lo and s[1] < lo) or (hi and s[0] > hi)):
            continue
        rows.append((s[0] if s else HIGH, rel, fm))
    rows.sort(key=lambda r: (r[0], r[1]))
    for _, rel, fm in rows[: args.limit]:
        when = as_str(fm.get("start")) or "?"
        if fm.get("end"):
            when += f"..{fm['end']}"
        if fm.get("approx") is True:
            when = "~" + when
        print(f"{when}  {fm.get('type', '-')}  {fm.get('layer', '-')}  {rel}")
    if len(rows) > args.limit:
        print(f"... {len(rows) - args.limit} more")


if __name__ == "__main__":
    main()
