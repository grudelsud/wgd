---
name: init
description: Install wgd into the current Obsidian vault (empty or with existing content). Creates the vault's schema, templates, CONTRIBUTING.md and CLAUDE.md section, offers a basic Obsidian configuration, and sets up git. Re-run after editing .wgd/schema.yaml to re-render. Never moves or edits notes.
argument-hint: "[vault path, defaults to the current directory]"
---

# wgd init

The vault is the argument if given, otherwise the current working directory. `WGD` is the plugin root, two directories above this skill's base directory. Every script is run as `uv run "$WGD/scripts/<script>.py" <vault> ...`.

## 1. Check the target

- Stop if the vault is the wgd plugin repo itself (it has `.claude-plugin/plugin.json` with `"name": "wgd"`). wgd is installed into a vault, never into its own source.
- Note whether this is a first install (no `.wgd/schema.yaml`) or a re-render, whether `.obsidian/` exists, and whether the vault is a git repo with uncommitted changes (`git status --porcelain`).

## 2. Offer the Obsidian setup (first install only, or when asked)

Ask the user whether to apply the basic Obsidian configuration. Explain it first. Settings are merged into the existing files in `.obsidian/`, and keys not listed here are left alone:

- `app.json`: attachments go to `attachments/`, new notes are created in `inbox/`, links use shortest `[[wikilinks]]`
- `templates.json`: the Templates core plugin uses `templates/` (wgd generates one template per type)
- `core-plugins.json`: enables Templates, Properties and Bases

Ask the user to close the vault in Obsidian first, because Obsidian overwrites its config when it exits.

## 3. Run

```
uv run "$WGD/scripts/init.py" <vault> [--obsidian]
```

The script keeps an existing schema and only refreshes the generated files: `templates/`, `views/Everything.base` (the Obsidian Base for browsing), the `wgd:schema` block in `CONTRIBUTING.md`, the `wgd` block in `CLAUDE.md`, and the type folders. If the schema has errors it prints them; fix them with the user, then run it again.

## 4. Git

- **Not a repo**: run `git init`, then commit everything with `wgd: init`. `init.py` has already added Obsidian's volatile files to `.gitignore`. The existing notes become the baseline that a backfill can be reverted to.
- **Already a repo**: commit only the files init touched (`.wgd/`, `templates/`, `views/Everything.base`, `CONTRIBUTING.md`, `CLAUDE.md`, `.gitignore`, changed `.obsidian/*.json`) with `wgd: init`, or `wgd: re-render` on a re-render. Don't sweep in the user's unrelated uncommitted changes. Mention them instead.

## 5. Report

Run `uv run "$WGD/scripts/validate.py" <vault> --summary` and tell the user:

- what was created or updated
- whether the Obsidian setup was applied
- the note counts

If any notes are not wgd content or are invalid, suggest `/wgd:discover` to work out which content types the vault needs, then `/wgd:backfill`. Otherwise suggest `/wgd:capture` to start adding content and `/wgd:add-type` for content that doesn't fit `note`, `context` or `person`.
