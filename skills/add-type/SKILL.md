---
name: add-type
description: Add a new content type to the current wgd vault (e.g. recipe, trip, meal, book). Drafts the type with the user, adds it to .wgd/schema.yaml, and regenerates its template, folder and the CONTRIBUTING.md rules.
argument-hint: "<type name> [what it is for]"
---

# wgd add-type

The vault is the current directory and must have `.wgd/schema.yaml`. If it doesn't, stop and suggest `/wgd:init`. `WGD` is the plugin root, two directories above this skill's base directory.

## 1. Understand the vault

Read `.wgd/schema.yaml` (including the header comment, which lists the field kinds) and `CONTRIBUTING.md`.

The name must be lowercase kebab-case and not already a type. If an existing type, or a `note` with a tag, already covers the need, say so and stop unless the user still wants the new type.

## 2. Draft the type with the user

Propose a complete draft and confirm it before writing anything:

- **description**: one line saying what belongs in this type, written so that capture and backfill can classify content by it
- **folder**: usually the plural name (`recipes`). Use `{yyyy}` (e.g. `trips/{yyyy}`) only for types that pile up over time.
- **default_layer**: one of the `layer` values in the schema
- **fields**: only what this type needs beyond the common fields, with kind (`text`, `url`, `bool`, `date`, `datetime`, `enum` with values, `list`, `links` with a target type) and whether each is required. Keep the list short, because every required field must be filled for every note of this type, including backfilled ones. A common field can be overridden, e.g. `start: {required: false}` for types that have no date.
- **body** (optional): a markdown skeleton for the template, e.g. `## Ingredients` / `## Method`

Example for `recipe`:

```yaml
  recipe:
    description: something cooked or to cook, with ingredients and method
    folder: recipes
    default_layer: life
    fields:
      servings:
        kind: text
      source_url:
        kind: url
      start:
        required: false
        description: when first cooked
    body: "## Ingredients\n\n## Method\n"
```

## 3. Write and render

1. Add the type under `types:` in `.wgd/schema.yaml` with Edit, so the file's comments are kept.
2. Run `uv run "$WGD/scripts/validate.py" . --schema` and fix any errors.
3. Run `uv run "$WGD/scripts/render.py" .`. It writes `templates/<name>.md`, adds a view for the type to `views/Everything.base`, creates the folder and refreshes the `CONTRIBUTING.md` and `CLAUDE.md` blocks.
4. Run `uv run "$WGD/scripts/validate.py" . --summary` to make sure existing notes are unaffected.
5. Commit `.wgd/schema.yaml`, `templates/`, `views/Everything.base`, `CONTRIBUTING.md` and `CLAUDE.md` with `wgd: add type <name>`.

## 4. Report

Show the template that was created. If a backfill left notes waiting for this type, suggest running `/wgd:backfill` again for them.

Changing or removing an existing type is not supported yet. Existing notes would need migrating, so tell the user rather than editing the type.
