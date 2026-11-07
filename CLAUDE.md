# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

wgd ("when grand*a died") is a personal lifelog built on Obsidian. It holds notes, people, contexts, and later bookmarks, health data and photos, all on a timeline, and lets the user query them as a graph that evolves through time.

- `docs/about.md` is the product vision.
- `docs/implementation.md` is the technical direction and the prior art already reviewed.
- `docs/plan.md` is the current phase 1 plan.

**This repo is the tool, never the content.** It is a Claude Code plugin named `wgd` that gets installed into a separate Obsidian vault. Never create vault content (notes, people, contexts) in this repo. Test vaults go in temp directories.

## Commands

```bash
uv run --with pytest --with pyyaml pytest tests/                 # all tests
uv run --with pytest --with pyyaml pytest tests/ -k apply        # a single test
claude plugin validate .                                         # check the plugin manifest

# use the plugin on a vault, running from inside the vault
claude --plugin-dir ~/Projects/personal/wgd                      # dev: loads skills from this repo
claude plugin marketplace add ~/Projects/personal/wgd && claude plugin install wgd@wgd --scope project
```

Each script under `scripts/` is a uv inline script (PyYAML) that takes the vault path as its first argument, e.g. `uv run scripts/validate.py <vault>`.

## Architecture

- **The vault owns its schema.** `/wgd:init` copies `defaults/schema.yaml` to `<vault>/.wgd/schema.yaml`. From then on the vault's copy is the source of truth, and `/wgd:add-type` and `/wgd:discover` extend it. The intended order for a vault with content is init → discover → (tidy) → backfill → tidy. Nothing in `scripts/` hardcodes types or fields; everything reads the vault's schema through `wgdlib.load_schema` and `wgdlib.fields_for`, which merges the common fields with a type's overrides.
- **Generated files**: `scripts/render.py` produces these from the schema, and re-running it is safe:
  - `templates/<type>.md`
  - `views/Everything.base`: an Obsidian Base with a timeline, an ongoing view and one view per type. wgd owns this file and overwrites it when the schema changes, because Obsidian rewrites `.base` YAML itself and markers wouldn't survive. Users customise by copying it; other files in `views/` (and later the visualisation plugin's files) are theirs
  - the type folders
  - the block between `<!-- wgd:schema:start/end -->` in the vault's `CONTRIBUTING.md`
  - the block between `<!-- wgd:start … -->` and `<!-- wgd:end -->` in the vault's `CLAUDE.md`

  Content outside those markers belongs to the user and is kept.
- **Skills and scripts**: skills (`skills/*/SKILL.md`) hold the judgement: classifying, inferring dates, talking to the user. Scripts hold everything deterministic:
  - `validate.py`: notes against the schema
  - `inventory.py`: backfill facts, including file birth times cached in `.wgd/cache/`
  - `apply.py`: merges frontmatter, moves notes with `git mv`, rewrites path-qualified links
  - `query.py`: filters by frontmatter, links, text and time overlap
  - `tidy.py`: files attachments under `attachments/<note name>/`, rewrites links that would break, prunes empty folders; `--due` counts `capture:` commits since the last `wgd: tidy`
  - `survey.py`: collects the signals `/wgd:discover` uses to propose types (folders, keys and values, tags, headings, link targets)
  - `init.py`: installs wgd into a vault

  Skills find the scripts as `<skill base dir>/../../scripts`.
- **Git is the revision log.** Every skill that writes ends with a commit in the vault, and a backfill commits once per batch so it can be reverted.
- **Dates** are partial ISO strings (`2019`, `2019-03`, `2019-03-12T10:00`), and the length of the string gives the precision. YAML is loaded with timestamps turned off (`wgdlib._StrLoader`) so dates stay strings the way Obsidian writes them. `query.py` compares spans by padding partial dates to their lowest and highest possible moments.
- **Frontmatter is flat** (scalars and lists only), because Obsidian Properties and Bases can't handle nested objects. Links in frontmatter are quoted `"[[Name]]"`.

## Domain rules

- Time granularity is mixed and fuzzy (`approx`, `end: ongoing`). A context such as "Ukraine war" spans time and groups dated notes.
- `visibility: sealed` (encrypted) is reserved. The validator rejects it and skills must never read sealed note bodies.
- Queries answer with context (what was happening around it, who was involved), not just a date.
- Deferred: the visualisation plugin, Oura and other feeds, photos, changing or removing a type, backfill of non-markdown files.
