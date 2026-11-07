---
name: discover
description: Scan the current vault's existing content and propose the set of content types worth defining for it (e.g. recipe, trip, meeting, book), with evidence, then add the ones the user accepts to .wgd/schema.yaml in one go. A guided version of add-type for a whole vault; run it after /wgd:init and before /wgd:backfill.
argument-hint: "[subfolder to limit the scan]"
---

# wgd discover

The vault is the current directory and must have `.wgd/schema.yaml`. If it doesn't, stop and suggest `/wgd:init`. `WGD` is the plugin root, two directories above this skill's base directory.

This skill only changes the schema and the files generated from it. It never touches notes. Backfill does that afterwards.

## 1. Survey

```
uv run "$WGD/scripts/survey.py" . [subfolder]
```

The report lists:

- folders, with note counts and sample filenames
- frontmatter keys, with their values when there are few distinct ones
- tags
- recurring headings, e.g. `## ingredients` in 40 notes
- the most-linked targets, marking those with no note behind them
- how many notes have a date in the filename
- non-markdown files

Also read `.wgd/schema.yaml`, so you know which types already exist.

## 2. Look at the clusters

A cluster is a group of notes that share a signal:

- a folder
- a frontmatter value (`category: book`, an old `type:`)
- a tag
- a set of headings
- a filename pattern, such as daily notes

For each cluster with real weight, read 3 to 5 notes. Use the samples from the report, plus `query.py . --text …` or grep. Note what the notes have in common: their shape, the fields they carry, and how they relate to time.

## 3. Decide what deserves a type

A cluster becomes a **type** when it has enough notes (about 10 or more, or the user cares about it) and at least one of these:

- **its own fields**: data that belongs in frontmatter, such as servings, rating, author or destination
- **its own structure**: recurring headings that make a good template body
- **its own place on the timeline**: trips span days, meetings are moments, books span the reading time

Otherwise it doesn't get a type:

- a group that only differs by topic stays a `note` with a tag, or a `context` if it is a period or project
- daily or journal notes are `note`s with a dated filename
- most-linked targets that are people or ongoing periods are `person` or `context` notes, which backfill will create

Keep the proposal small: usually 2 to 6 new types. A type you leave out can be added later with `/wgd:add-type`.

## 4. Propose

Show one table: proposed type | evidence (cluster, note count, signals) | folder | fields | default layer | template body. Below it, list what was deliberately **not** made a type and what it becomes (tag, context, plain note), so the user can overrule.

Draft each type by the rules in `../add-type/SKILL.md`, step 2: kebab-case name, a description written for classification, few required fields. When notes already carry a frontmatter key for a field, keep that key's name, so backfill keeps the existing values. If the key is a date about the content (`date_read`, `trip_date`), map it to `start`/`end` instead.

The user accepts, edits or rejects each row. Nothing is written before that.

## 5. Write

1. Add all accepted types under `types:` in `.wgd/schema.yaml` with Edit, keeping the comments.
2. Run `uv run "$WGD/scripts/validate.py" . --schema`, then `uv run "$WGD/scripts/render.py" .`.
3. Write `.wgd/cache/discover.md` for backfill. For each type, give the cluster signals that identify it, e.g. "folder `Cooking/`, tag `#recipe`, heading `## Ingredients`", and the frontmatter key mappings, e.g. "`date_read` → `end`". Add the not-a-type decisions: which tags, contexts and people to use.
4. Commit `.wgd/schema.yaml`, `templates/`, `views/Everything.base`, `CONTRIBUTING.md` and `CLAUDE.md` with `wgd: add types <a>, <b>, … (discover)`.

## 6. Hand over

Show the new templates. Offer to run `/wgd:tidy` now, so that attachments are grouped by their note before the restructuring starts. Then suggest `/wgd:backfill`, which reads `.wgd/cache/discover.md` to classify the notes.
