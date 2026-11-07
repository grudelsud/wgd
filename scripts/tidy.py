# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""Keep a vault in order for /wgd:tidy: group attachments by the note that uses them, prune empty folders.

    tidy.py VAULT                 plan: print a report, write .wgd/cache/tidy.json
    tidy.py VAULT --apply PLAN    move attachments, rewrite links, remove empty folders listed in PLAN
    tidy.py VAULT --due [--every N]   is a tidy due? (N capture commits since the last "wgd: tidy")

An attachment is any non-markdown file a note links to. One note:
attachments/<note name>/<file>. Several notes: attachments/_shared/<file>. Links in the
referencing notes are rewritten when they would no longer resolve (path links, relative
markdown links, or names that become ambiguous). Broken links whose file name matches exactly
one file in the vault are repaired. Files no note links to are reported, never moved.
Files under inbox/ and templates/ are left alone. Does not commit.
"""

import argparse
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote, unquote

from apply import move
from wgdlib import load_schema

WIKI_RE = re.compile(r"(!?)\[\[([^\]|#]+?)(#[^\]|]*)?(\|[^\]]*)?\]\]")
MD_RE = re.compile(r"(!?)\[([^\]]*)\]\(\s*(<[^>]+>|[^)\s]+)((?:\s+\"[^\"]*\")?)\s*\)")
NOT_ATTACHMENTS = {".md", ".canvas", ".base"}
# a link that resolves to nothing is a missing attachment only with one of these suffixes;
# otherwise it is a link to a note not written yet, like [[Dr. Smith]] or [[v1.2 release]]
FILE_TYPES = set(
    ".avif .bmp .gif .heic .jpeg .jpg .png .svg .tif .tiff .webp "
    ".3gp .aac .flac .m4a .mp3 .ogg .opus .wav .mkv .mov .mp4 .ogv .webm "
    ".pdf .epub .txt .csv .tsv .json .xml .html .htm .doc .docx .xls .xlsx .ppt .pptx .odt .ods .odp .rtf "
    ".zip .gz .tar .7z .key .numbers .pages .excalidraw .ics .vcf .gpx .kml".split())
LEFT_ALONE = ("inbox/", "templates/")
SHARED, UNLINKED, CACHE = "_shared", "_unlinked", ".wgd/cache/tidy.json"
JUNK = {".DS_Store", "Thumbs.db"}


def walk_files(vault):
    for dirpath, dirnames, filenames in os.walk(vault):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fn in filenames:
            if not fn.startswith(".") and fn not in JUNK:
                yield (Path(dirpath) / fn).relative_to(vault).as_posix()


def is_attachment(rel):
    return Path(rel).suffix.lower() not in NOT_ATTACHMENTS and Path(rel).suffix != ""


class Files:
    def __init__(self, vault):
        self.all = set(walk_files(vault))
        self.by_name = defaultdict(list)
        for rel in self.all:
            self.by_name[posixpath.basename(rel)].append(rel)

    def by_basename(self, name, note):
        hits = self.by_name.get(name, [])
        if len(hits) > 1:  # Obsidian prefers the copy next to the note
            near = [h for h in hits if posixpath.dirname(h) == posixpath.dirname(note)]
            return near[0] if near else sorted(hits)[0]
        return hits[0] if hits else None

    def is_note(self, target):
        """An unresolved link with a dot that is a note link, existing ([[spatial.energy]] opens spatial.energy.md) or not."""
        return (f"{target}.md" in self.all or f"{posixpath.basename(target)}.md" in self.by_name
                or Path(target).suffix.lower() not in FILE_TYPES)


def find_refs(vault, files):
    """Every link from a note to an attachment: dicts with note, span, resolved path and how to rewrite it."""
    refs, broken = [], []
    for note in sorted(r for r in files.all if r.endswith(".md")):
        text = (vault / note).read_text(errors="replace")
        for m in WIKI_RE.finditer(text):
            target = m.group(2).strip()
            if not is_attachment(target):
                continue
            if "/" in target:
                path, style = (target, "path") if target in files.all else (files.by_basename(posixpath.basename(target), note), "repair")
            else:
                path, style = files.by_basename(target, note), "name"
            if not path and files.is_note(target):
                continue
            ref = {"note": note, "span": m.span(), "kind": "wiki", "path": path, "style": style, "groups": m.groups()}
            (refs if path else broken).append(ref)
        for m in MD_RE.finditer(text):
            raw = m.group(3)
            target = unquote(raw[1:-1] if raw.startswith("<") else raw)
            if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I) or not is_attachment(target.split("#")[0]):
                continue
            target = target.split("#")[0]
            relative = posixpath.normpath(posixpath.join(posixpath.dirname(note), target))
            if "/" not in target and target in files.by_name:
                path, style = files.by_basename(target, note), "name"
            elif relative in files.all:
                path, style = relative, "relative"
            elif target.lstrip("/") in files.all:
                path, style = target.lstrip("/"), "path"
            else:
                path, style = files.by_basename(posixpath.basename(target), note), "repair"
            if not path and files.is_note(target):
                continue
            ref = {"note": note, "span": m.span(), "kind": "md", "path": path, "style": style, "groups": m.groups()}
            (refs if path else broken).append(ref)
    return refs, broken


def plan(vault):
    schema = load_schema(vault)
    files = Files(vault)
    refs, broken = find_refs(vault, files)
    parents = defaultdict(set)
    for ref in refs:
        if not ref["note"].startswith(LEFT_ALONE):
            parents[ref["path"]].add(ref["note"])

    moves, unlinked, claimed = [], [], set(files.all)
    for rel in sorted(files.all):
        if not is_attachment(rel) or rel.startswith(LEFT_ALONE):
            continue
        notes = sorted(parents.get(rel, ()))
        if not notes:
            if not rel.startswith(f"attachments/{UNLINKED}/") and not any(r["path"] == rel for r in refs):
                unlinked.append(rel)
            continue
        name = posixpath.basename(rel)
        if len(notes) == 1:
            folder = f"attachments/{Path(notes[0]).stem}"
        else:
            folder = f"attachments/{SHARED}"
            if posixpath.dirname(rel) in {f"attachments/{Path(n).stem}" for n in notes}:
                folder = posixpath.dirname(rel)  # already filed under one of its notes: leave it
        if posixpath.dirname(rel) == folder:
            continue
        dest, n = f"{folder}/{name}", 1
        while dest in claimed:
            dest = f"{folder}/{Path(name).stem} {n}{Path(name).suffix}"
            n += 1
        claimed.add(dest)
        moves.append({"from": rel, "to": dest, "notes": notes})

    moved = {m["from"] for m in moves}
    remaining = set()  # every file that stays, dotfiles included, so a .gitkeep keeps its folder
    for dirpath, dirnames, filenames in os.walk(vault):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        remaining |= {(Path(dirpath) / f).relative_to(vault).as_posix() for f in filenames if f not in JUNK}
    remaining -= moved
    protected = {"attachments", "inbox", "templates", "views"} | {
        (t or {}).get("folder", "").split("{")[0].strip("/") for t in schema["types"].values()}
    empty_dirs = []
    for dirpath, dirnames, _ in os.walk(vault, topdown=False):
        rel = Path(dirpath).relative_to(vault).as_posix()
        if rel == "." or any(p.startswith(".") for p in Path(rel).parts) or rel in protected:
            continue
        if not any(f == rel or f.startswith(rel + "/") for f in remaining):
            empty_dirs.append(rel)
    # keep only the outermost folders: removing them removes their children
    empty_dirs = sorted(d for d in empty_dirs if not any(d.startswith(o + "/") for o in empty_dirs))

    repairs = sum(1 for r in refs if r["style"] == "repair")
    return {
        "moves": moves,
        "unlinked": unlinked,
        "empty_dirs": empty_dirs,
        "repairs": repairs,
        "broken": [{"note": r["note"], "link": r["groups"][1] if r["kind"] == "wiki" else r["groups"][2]} for r in broken],
        "inbox": sum(1 for f in files.all if f.startswith("inbox/")),
    }


def link_target(ref, new_path, unique):
    style = ref["style"]
    if ref["kind"] == "wiki":
        if style == "name" and unique:
            return posixpath.basename(new_path)
        return new_path
    if style == "relative":
        return posixpath.relpath(new_path, posixpath.dirname(ref["note"]) or ".")
    if style == "name" and unique:
        return posixpath.basename(new_path)
    return new_path


def render_link(ref, target):
    g = ref["groups"]
    if ref["kind"] == "wiki":
        embed, _, heading, alias = g
        return f"{embed}[[{target}{heading or ''}{alias or ''}]]"
    embed, alt, raw, title = g
    if raw.startswith("<"):
        target = f"<{target}>"
    else:
        target = quote(target, safe="/")
    return f"{embed}[{alt}]({target}{title})"


def apply_plan(vault, plan_data):
    files = Files(vault)
    refs, _ = find_refs(vault, files)
    moves = {m["from"]: m["to"] for m in plan_data.get("moves", [])}
    final_names = defaultdict(int)
    for rel in files.all:
        final_names[posixpath.basename(moves.get(rel, rel))] += 1

    for src, dest in moves.items():
        if (vault / dest).exists():
            print(f"{src}: {dest} already exists, skipped")
            continue
        move(vault, src, dest)
        print(f"{src} -> {dest}")

    edits = defaultdict(list)
    for ref in refs:
        new_path = moves.get(ref["path"], ref["path"])
        unique = final_names[posixpath.basename(new_path)] == 1
        if new_path == ref["path"] and ref["style"] != "repair" and (ref["style"] != "name" or unique):
            continue
        edits[ref["note"]].append((ref["span"], render_link(ref, link_target(ref, new_path, unique))))
    for note, changes in edits.items():
        note = moves.get(note, note)
        path = vault / note
        text = path.read_text()
        for (start, end), new in sorted(changes, reverse=True):
            text = text[:start] + new + text[end:]
        path.write_text(text)
        print(f"rewrote {len(changes)} link(s) in {note}")

    for rel in plan_data.get("empty_dirs", []):
        d = vault / rel
        if not d.is_dir():
            continue
        leftovers = [p for p in d.rglob("*") if p.is_file() and p.name not in JUNK]
        if leftovers:
            print(f"{rel}/ is not empty, kept")
            continue
        shutil.rmtree(d)
        print(f"removed {rel}/")


def due(vault, every):
    log = subprocess.run(["git", "log", "--format=%s"], cwd=vault, capture_output=True, text=True)
    if log.returncode != 0:
        return "unknown (not a git repo)"
    captures = 0
    for subject in log.stdout.splitlines():
        if subject.startswith("wgd: tidy"):
            break
        captures += subject.startswith("capture:")
    return f"{'due' if captures >= every else 'not due'} ({captures} captures since the last tidy, threshold {every})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vault")
    ap.add_argument("--apply")
    ap.add_argument("--due", action="store_true")
    ap.add_argument("--every", type=int, default=10)
    args = ap.parse_args()
    vault = Path(args.vault).resolve()

    if args.due:
        print(due(vault, args.every))
        return 0
    if args.apply:
        apply_plan(vault, json.loads(Path(args.apply).read_text()))
        return 0

    p = plan(vault)
    out = vault / CACHE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(p, indent=1, ensure_ascii=False))
    by_note = defaultdict(int)
    for m in p["moves"]:
        by_note[m["to"].rsplit("/", 1)[0]] += 1
    print(f"{len(p['moves'])} attachments to file into {len(by_note)} folders:")
    for folder, n in sorted(by_note.items()):
        print(f"  {folder}/ <- {n}")
    print(f"{p['repairs']} broken links repairable by file name; {len(p['broken'])} broken links not repairable")
    for b in p["broken"]:
        print(f"  {b['note']}: {b['link']}")
    print(f"{len(p['unlinked'])} files no note links to:")
    for u in p["unlinked"]:
        print(f"  {u}")
    print(f"{len(p['empty_dirs'])} empty folders (after the moves):")
    for d in p["empty_dirs"]:
        print(f"  {d}/")
    print(f"{p['inbox']} files waiting in inbox/")
    print(f"plan written to {CACHE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
