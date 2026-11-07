---
name: tidy
description: Keep the current wgd vault in order. Files attachments into attachments/<note name>/ next to the note that uses them (or attachments/_shared/), fixes the links, repairs broken attachment links, reports unlinked files and offers to remove empty folders. Useful after Obsidian Web Clipper or "download attachments" dumps images into one folder. Run it manually, after about 10 captures (capture suggests it), or after discover or backfill.
argument-hint: ""
---

# wgd tidy

The vault is the current directory and must have `.wgd/schema.yaml`. If it doesn't, stop and suggest `/wgd:init`. `WGD` is the plugin root, two directories above this skill's base directory.

Tidy moves attachments and removes folders. It never edits a note except to rewrite links that point to a moved or broken attachment.

## 0. Preconditions

`git status --porcelain` must be empty, so the tidy can be reverted as one commit. If it isn't, offer to commit the current state first, or stop. Ask the user to close Obsidian, or at least not to edit anything, while files move.

## 1. Plan

```
uv run "$WGD/scripts/tidy.py" .
```

This writes `.wgd/cache/tidy.json` and prints:

- **attachments to file**: every non-markdown file a note links to.
  - Linked from one note, it goes to `attachments/<note name>/`.
  - Linked from several, it goes to `attachments/_shared/`.

  Files under `inbox/` and `templates/` are left alone.
- **broken links**: some can be repaired because exactly one file in the vault has that name. These are typically relative links broken when a note moved. The rest are listed for the user.
- **unlinked files**: files no note links to. They are never moved automatically. Files already in `attachments/_unlinked/` are not listed again.
- **empty folders**: folders that are empty, or that will be once the moves are done. Folders wgd needs (`attachments/`, `inbox/`, `templates/`, `views/`, the type folders) are never listed.
- **inbox**: the number of files waiting in `inbox/`.

Also run `uv run "$WGD/scripts/validate.py" . --summary` for the health line.

## 2. Review with the user

Summarise rather than dumping the whole list: "112 attachments into 37 article folders, 4 shared, 3 links repaired". Show the full list only when it is short or the user asks for it.

Then ask, separately:

1. whether to apply the attachment moves
2. which **empty folders** to remove. List them all, since this is the one destructive step.
3. what to do with each **unlinked file**, or with all of them at once:
   - leave it
   - move it to `attachments/_unlinked/`, by adding `{"from": ..., "to": "attachments/_unlinked/<name>"}` entries to `moves`
   - delete it with `git rm`, or `rm` if it is untracked, but only when the user explicitly says so

Remove from the plan JSON anything the user rejects: entries from `moves`, folders from `empty_dirs`.

## 3. Apply

```
uv run "$WGD/scripts/tidy.py" . --apply .wgd/cache/tidy.json
```

The script:

- moves the files, with `git mv` when they are tracked
- rewrites only the links that would stop resolving: relative and path links, names that become ambiguous, and repaired links. It keeps each link's style (wikilink or markdown, embed, alias, size).
- removes the approved empty folders, skipping any that are no longer empty

Run `uv run "$WGD/scripts/tidy.py" .` again. It should report no attachments left to file and no repairs.

## 4. Commit and report

Commit everything with `wgd: tidy (<n> attachments, <k> folders removed)`. This subject is what `tidy.py --due` counts captures from.

Report what moved, what was removed, and the broken links that still need a human. If there are notes that are not wgd content or are invalid, suggest `/wgd:backfill`. If files are waiting in `inbox/`, suggest `/wgd:capture`.
