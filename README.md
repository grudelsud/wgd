# wgd

"when grand*a died". You get old, you look back, and you can't remember whether that thing happened before or after grandma got ill, or who you were with, or what you were doing at work back then. wgd is a lifelog that tries to answer that.

It's a Claude Code plugin that turns an Obsidian vault into a timeline. Notes, people and contexts (e.g. "Ukraine war", 2022-02 to ongoing) get typed frontmatter with fuzzy dates. You can then ask questions and get context back, not just a date.

Why I'm doing it is in [docs/about.md](docs/about.md), and how it works is in [docs/implementation.md](docs/implementation.md).

> Candidly: most of the code and docs here, this README included, were written by Claude (Claude Code) from my notes and direction, then tested on my own vault. Read it with that in mind.

## what it does

- **your vault, your schema**: types and fields live in `.wgd/schema.yaml` inside the vault, and you can add your own (recipe, trip, meal...)
- **time is fuzzy**: dates can be `2019`, `2019-03` or `2019-03-12T10:00`, flagged `approx`, or `end: ongoing`
- **plain Obsidian**: flat frontmatter, `[[links]]`, templates, and a Base (`views/Everything.base`) with a timeline, what's ongoing, and one view per type
- **git is the history**: every skill that writes ends with a commit, so you can always revert

## skills

| skill | |
|---|---|
| `/wgd:init` | install into a vault (empty or not); re-run after editing the schema |
| `/wgd:discover` | look at what's already in the vault and propose types |
| `/wgd:add-type` | add a single type |
| `/wgd:capture` | a memory, a quick tag ("restless legs last night"), a URL, or whatever is in `inbox/` |
| `/wgd:backfill` | bring existing notes in line, batch by batch, one commit each |
| `/wgd:tidy` | file attachments next to their notes, fix links, drop empty folders |
| `/wgd:ask` | "when did I meet X and how do I know them?" |

## install

You need [Claude Code](https://claude.com/claude-code), [uv](https://docs.astral.sh/uv/) and git. Obsidian is optional, but it's the point.

From inside your vault:

```bash
claude plugin marketplace add grudelsud/wgd
claude plugin install wgd@wgd --scope project
claude
```

then `/wgd:init`. If the vault already has content, go init → discover → tidy → backfill → tidy. Backfill moves things around, so make sure the vault is committed first (init sets up git if it isn't).

## develop

The repo is the tool, never the content: test vaults go in temp directories.

```bash
claude --plugin-dir ~/path/to/wgd                         # run from a vault, loads skills from your checkout
uv run --with pytest --with pyyaml pytest tests/           # tests
claude plugin validate .
```

Skills (`skills/*/SKILL.md`) do the judgement, and the scripts in `scripts/` do everything deterministic. More in [CLAUDE.md](CLAUDE.md).

## not yet

The timeline and graph visualisation, Oura and other feeds, photos, encrypted (`sealed`) notes, and changing or removing a type. See [docs/plan.md](docs/plan.md).
