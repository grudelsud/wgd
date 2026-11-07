---
name: backfill
description: Bring the existing content of the current vault in line with wgd's CONTRIBUTING.md. Infers type, dates, layer, people and contexts for each note, moves notes into their type's folder, and applies changes batch by batch after the user approves each one. Expect it to restructure the vault; every batch is one git commit that can be reverted.
argument-hint: "[subfolder to limit the run]"
---

# wgd backfill

The vault is the current directory and must have `.wgd/schema.yaml`. If it doesn't, stop and suggest `/wgd:init`. `WGD` is the plugin root, two directories above this skill's base directory.

## 0. Preconditions

- `git status --porcelain` must be empty, so that every batch can be reverted cleanly. If it isn't, offer to commit the current state as `wgd: snapshot before backfill`, or stop.
- Read `CONTRIBUTING.md` and `.wgd/schema.yaml`. They are the rules this run applies, including any types added with `/wgd:add-type` or `/wgd:discover`.
- Read `.wgd/cache/discover.md` if it exists. It maps folders, tags, headings and frontmatter keys to types, and records which clusters stay tags or contexts.
- If the schema has only the default types and there are many notes, suggest running `/wgd:discover` first. Continue if the user declines.

## 1. Inventory

```
uv run "$WGD/scripts/inventory.py" . [subfolder]
```

This writes `.wgd/cache/inventory.json`, listing every note that doesn't conform with:

- its birth time, which is recorded once and kept across runs
- its mtime
- any date found in the filename
- its existing frontmatter and validation errors

It also lists duplicate note names and notes that contain path-qualified links. Tell the user the counts and how many batches of about 20 notes that makes.

## 2. Infer, one batch at a time

Read each note in the batch: its frontmatter, and the body up to about 80 lines. Then decide:

- **type**: use the signals and key mappings from `discover.md` when present, otherwise the schema type whose description fits the content best, otherwise `note`.
  - If the existing frontmatter has a `type` value that isn't in the schema, move that value into `tags`.
  - When notes clearly form a kind the schema lacks (recipes, trips, books), don't force them into `note`. Set them aside and count them.
- **start / end / approx**: take the first source that exists, and record which one you used:
  1. existing frontmatter dates (`date`, `start`, `created`, `day`, …)
  2. `filename_date` from the inventory
  3. a date stated in the body that the note is about
  4. the inventory `birthtime`, at day precision with `approx: true`

  Add `end` only when the content describes a span.
- **layer**: from the content. Use the type's `default_layer` when it is unclear.
- **people / contexts**: only when the note clearly names them. Match existing notes with `query.py --type person|context`. Collect the new people and contexts the batch needs and propose them, rather than creating one per mention.
- **visibility**: `private`. **source**: `backfill`. **source_ref**: the original path.
- **created**: the inventory `birthtime`.
- Keep every existing frontmatter key the schema doesn't know about (`aliases`, `cssclasses`, …).

## 3. Review with the user

Show one table per batch: path → destination, type, start / end (source), layer, people and contexts. Below it, list the new people and contexts to create, the notes set aside for a missing type, and any duplicate names involved.

The user approves, edits or skips rows. Nothing is written before approval.

Duplicate names: moving one copy can change which note `[[Name]]` resolves to. Propose a rename, using `"to"` in the plan, or skip it. Never pick silently.

## 4. Apply

1. Create the approved new person and context notes from their templates, in their folders.
2. Write the approved rows to `.wgd/cache/batch-<n>.json` as `[{"path": ..., "frontmatter": {...}, "to": optional}]`. Frontmatter keys are merged over the existing ones; `null` removes a key.
3. Run `uv run "$WGD/scripts/apply.py" . .wgd/cache/batch-<n>.json --dry-run` and check the moves match the review.
4. Run it without `--dry-run`. The script:
   - writes the frontmatter
   - moves each note to its type folder, keeping the filename, with `git mv`
   - rewrites path-qualified links to moved notes

   It never edits a note's body otherwise.
5. Fix anything it reports as invalid by editing frontmatter only, then re-run `validate.py . <files>`.
6. Commit with `wgd: backfill batch <n> (<k> notes)`.

Then move on to the next batch.

## 5. Wrap up

Report:

- the notes backfilled
- the notes skipped
- the groups set aside, e.g. "14 notes look like recipes", each with a suggested `/wgd:add-type <name>`. After adding the type, re-run `/wgd:backfill` to pick them up.
- non-markdown files outside `attachments/` (find them with `find . -type f ! -name '*.md' -not -path './.*' -not -path './attachments/*'`). They are listed only; this version moves `.md` files only.

Suggest `/wgd:tidy` to finish. It repairs relative attachment links that broke when notes moved, groups attachments under their notes, and offers to remove the folders the backfill emptied.

To undo a batch: `git revert <commit>`.
