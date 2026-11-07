---
name: capture
description: Add content to the current wgd vault - a free-text memory, a quick tag ("restless legs last night"), a URL to bookmark, or files dropped in inbox/. Turns each into a typed note with dates, layer, people and contexts, following the vault's CONTRIBUTING.md.
argument-hint: "<text, URL or inbox file>  (no argument: process inbox/)"
---

# wgd capture

The vault is the current directory and must have `.wgd/schema.yaml`. If it doesn't, stop and suggest `/wgd:init`. `WGD` is the plugin root, two directories above this skill's base directory.

Read `CONTRIBUTING.md` and `.wgd/schema.yaml` first. They define the types, folders, fields and filename rules. Don't rely on memory of the default schema, because the vault may have added types.

## 1. Work out what is being captured

- Text or a tag: one note, or several if the text clearly describes several things.
- A URL: a bookmark, which is a `note` with `url` unless the schema has a better type. Fetch the page title if you can. Record why it was saved if the user said.
- No argument: every file in `inbox/`. A markdown file becomes the note body. Any other file moves to `attachments/<note name>/` and the note embeds it with `![[file]]`.

## 2. Fill the frontmatter

- **type**: the schema type whose description fits best, otherwise `note`.
- **start / end / approx**: when it happened, not when it was captured. Use only the precision you have ("last spring" → `start: 2026-03`, `end: 2026-05`, `approx: true`). Resolve relative dates against today. `end: ongoing` is for things that have not ended.
- **layer**: from the schema values, or the type's `default_layer`.
- **people / contexts**: search existing notes first (`uv run "$WGD/scripts/query.py" . --type person --text <name>`, same with `--type context`), including near-miss spellings. Propose any person or context that doesn't exist yet and create it, from its template, only once the user confirms.
- **visibility**: `private` unless the user says otherwise. Never create `sealed` notes; they are not supported yet.
- **source**: `manual` for typed text, `file` for inbox files. **source_ref**: the URL or the original file name.
- **created**: now (`date +%Y-%m-%dT%H:%M`).

## 3. Write

- Start from `templates/<type>.md`. Drop empty optional fields and fill the rest, keeping the template's field order. Quote links: `["[[Valentina]]"]`.
- Name and place the file as `CONTRIBUTING.md` says, e.g. `notes/2026/2026-03 Lisbon offsite.md`. Never overwrite an existing file.
- Keep the user's words in the body. Don't embellish.
- Move processed inbox files with `git mv` when they are tracked, `mv` otherwise.

## 4. Validate and commit

Run `uv run "$WGD/scripts/validate.py" . <each written file>` and fix whatever it reports. Then commit only the files this capture touched, with `capture: <title>` (or `capture: <n> notes from inbox`).

Reply with one line per note: its `[[link]]`, type, and when.

Then run `uv run "$WGD/scripts/tidy.py" . --due`. If it says `due`, mention it in one line and offer to run `/wgd:tidy` now.
