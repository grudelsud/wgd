# Contributing to this vault

This vault is organised by wgd. These rules apply to people and agents alike. Everything between the `wgd:schema` markers is generated from `.wgd/schema.yaml`. Edit the schema (or run `/wgd:add-type`), not that block. The rest of this file is yours to change.

## Rules

- Every note has frontmatter with a `type` from the schema below, and lives in that type's folder.
- Time is what the note is about, not when it was written. Use `start` (and `end` for spans) with only as much precision as you know: `2019`, `2019-03`, `2019-03-12`. Add `approx: true` when the bounds are fuzzy. Use `end: ongoing` for things that have not ended.
- Link people and contexts through the `people` and `contexts` lists, quoted: `["[[Valentina]]"]`. Create the person or context note first if it does not exist.
- Name dated notes `<start> <title>.md` (e.g. `2022-02-24 Ukraine war starts.md`); name people and contexts by their name. Avoid `[ ] # ^ | \ / :` in filenames.
- Keep filenames when moving notes, so `[[links]]` keep resolving.
- New files to process go in `inbox/`. Images and documents go in `attachments/<note name>/` next to the note that uses them, or in `attachments/_shared/` when several notes use them. `/wgd:tidy` keeps this in order.
- Every change is a git commit, so the history of a note is `git log -- <note>`.

<!-- wgd:schema:start -->
<!-- wgd:schema:end -->
