# plan: phase 1

Phase 1 is the smallest wgd that can be installed into any Obsidian vault, empty or already full, and then structure it, ingest content and answer questions. Visualisation, Oura, photos and encryption come later. The schema is shaped so they can be added without migrating notes.

## principles

- **This repo is the tool, never the content.** wgd is a Claude Code plugin. You open a vault and install wgd into it.
- **The vault owns its schema.** `.wgd/schema.yaml` in the vault is the source of truth. Templates, `CONTRIBUTING.md` and the `CLAUDE.md` section are all generated from it. Adding a content type means editing the schema and regenerating.
- **Git is the revision log.** Every wgd write is a commit, and restructuring is reverted with `git revert`.

## install and use

Run these from inside the vault:

| mode | command | edits in this repo take effect |
|---|---|---|
| dev | `claude --plugin-dir ~/Projects/personal/wgd` | next session |
| installed | `claude plugin marketplace add ~/Projects/personal/wgd`<br>`claude plugin install wgd@wgd --scope project` | after `claude plugin update` |

Then run `/wgd:init`. For a vault that already has content, follow it with `/wgd:discover` and then `/wgd:backfill`.

## what wgd puts in a vault

```
.wgd/schema.yaml        source of truth for types and fields
.wgd/cache/             backfill inventory (gitignored)
CONTRIBUTING.md         rules for people and agents; the wgd block is generated
CLAUDE.md               wgd section (generated): follow CONTRIBUTING.md, validate, commit
templates/<type>.md     generated; also used by Obsidian's Templates core plugin
notes/ contexts/ people/ inbox/   plus one folder per added type
attachments/<note name>/      attachments grouped by the note that uses them (_shared/ when several do)
.obsidian/*.json        optional; init offers to merge in folder and template settings
```

## default schema

Fields are flat, using scalars or lists only, because Obsidian's Properties panel and Bases can't handle nested objects. Links are quoted (`"[[Name]]"`) so the graph tracks them and renames update them.

Common fields:

| field | kind | required | notes |
|---|---|---|---|
| `type` | enum | yes | one of the schema's types |
| `start` | date | yes (except person) | partial ISO 8601: `2024`, `2024-03`, `2024-03-12`, `2024-03-12T10:00`. How much of the date is written gives the precision. |
| `end` | date | no | same format, or `ongoing`. Leave it out for a point in time. |
| `approx` | bool | no | `true` when the bounds are fuzzy |
| `layer` | enum | yes | `life` \| `work` \| `health` \| `knowledge` \| `world` |
| `contexts` | links → context | no | |
| `people` | links → person | no | |
| `visibility` | enum | yes | `private` \| `shared` \| `public`. `sealed` is reserved for encrypted notes. |
| `shared_with` | links → person | if `shared` | |
| `source` | text | yes | `manual`, `file`, `backfill`; later `oura`, … |
| `source_ref` | text | no | original path, URL or feed id |
| `created` | datetime | yes | when the item entered the vault, not when it happened |
| `tags` | list | no | |

Default types:

| type | folder | extra |
|---|---|---|
| `note` | `notes/{yyyy}` | `url` (a bookmark is a note with a url) |
| `context` | `contexts` | a span of time that groups notes, e.g. "Ukraine war", `start: 2022-02`, `end: ongoing` |
| `person` | `people` | `start` is optional and means "when we met" |

## skills

All skills follow the vault's `CONTRIBUTING.md` and run `scripts/validate.py` after writing.

- **`/wgd:init`**:
  - copies the default schema if the vault has none
  - renders templates, `CONTRIBUTING.md`, `CLAUDE.md` and folders
  - **offers** an Obsidian setup: attachments folder, new notes in `inbox/`, templates folder, core plugins
  - runs `git init` if needed and commits
  - in a vault with content, reports how many notes don't conform and suggests a backfill

  Init never moves notes. Re-running it is safe.
- **`/wgd:add-type <name>`**: drafts the type with the user (purpose, fields, folder, default layer), adds it to the schema, re-renders, validates and commits.
- **`/wgd:discover [path]`**: surveys existing content: folders, frontmatter keys and values, tags, recurring headings, most-linked targets. It proposes a small set of types, each with its evidence, plus what should stay a tag or context. The accepted types are added in one commit, and it leaves notes for backfill in `.wgd/cache/discover.md`. It never touches notes.
- **`/wgd:capture`**: turns text, a tag, a URL or a file in `inbox/` into a typed note. It reuses existing people and contexts, confirms any new ones, validates and commits.
- **`/wgd:ask`**: filters on frontmatter, searches note text, expands one hop through links and overlapping time spans, and answers with context and `[[links]]`. Read-only; it never reads sealed notes.
- **`/wgd:backfill [path]`**: restructures existing content to match the contributing rules.
  - requires a clean git tree
  - records each file's birth time before moving anything
  - infers type from the content
  - infers dates from the first source available: existing frontmatter, a date in the filename, a date in the body, then the file's creation date (marked `approx`)
  - infers layer, people and contexts from the content
  - moves each file to its type's folder, keeping the filename so links still resolve
  - shows a table per batch of about 20 files and applies only what is approved
  - uses `.wgd/cache/discover.md` to classify notes when it exists
  - suggests `/wgd:add-type` for groups of files that don't fit any type
  - handles `.md` only and never edits bodies, except to fix path-qualified links

- **`/wgd:tidy`**: keeps the vault in order. It runs on demand; capture suggests it after 10 captures, and discover and backfill offer it when they finish.
  - moves each attachment to `attachments/<note name>/`, or to `attachments/_shared/` when several notes use it. This fixes clipper dumps such as Web Clipper's single folder.
  - rewrites only the links that would break, and repairs broken links when exactly one file has that name
  - reports unlinked files and moves them only with approval
  - proposes removing empty folders
  - commits once as `wgd: tidy`

## deferred

- **Sealed notes**: encrypt the body only, for example with age, and keep the frontmatter plain so the timeline still works.
- **Oura feed**: `source: oura`, writing `layer: health` notes.
- **Photos**: linked through `source_ref`, never copied into git.
- **Visualisation plugin**: `start`/`end`/`approx` place items on the timeline, `layer` switches layers on and off, and `contexts`/`people` become graph edges.
- **Changing or removing a type** after it has been added.
- **Backfill of non-markdown files.**

## open decisions

- Whether `layer` should allow more than one value. It is single-valued for now.
