---
name: ask
description: Answer a question from the current wgd vault with context, not just facts - "when did I meet X and how do I know them?", "what do I know about energy saving?", "when did we visit the Maldives, and what was I doing then?". Read-only.
argument-hint: "<question>"
---

# wgd ask

The vault is the current directory and must have `.wgd/schema.yaml`. `WGD` is the plugin root, two directories above this skill's base directory. This skill is **read-only**: it never writes, moves or commits anything.

## 1. Find the anchors

Turn the question into people, contexts, topics, types, layers and time ranges, then search:

```
uv run "$WGD/scripts/query.py" . --link "Valentina"         # notes linking a person or context
uv run "$WGD/scripts/query.py" . --text "maldives"          # words in path, frontmatter or body
uv run "$WGD/scripts/query.py" . --type person --text marco
uv run "$WGD/scripts/query.py" . --from 2021 --to 2022-06 --layer work
```

Filters combine. Results come out ordered by time. Try synonyms and other spellings before concluding nothing is there. Grep is fine for anything `query.py` can't express.

## 2. Expand the context, one hop

For the anchor notes that matter:

- read them, plus the person and context notes they link to
- run `query.py . --overlaps <note>` to find what else was going on at the same time. This answers "what was I doing by then?"
- for a person, look for the earliest note linking them and at their `start`, which is when you met. Those notes give the circumstances of the meeting.

Don't widen past one hop unless the question asks for it.

## 3. Answer

- Lead with the direct answer, then give the context: what was happening around it, who was involved, and which contexts it belongs to.
- Keep things in time order and keep the precision honest. `approx` dates are "around".
- Cite every claim with the note's `[[link]]`.
- Say when the vault doesn't contain the answer, and suggest `/wgd:capture` if the user wants to record it.
- Never read the body of notes with `visibility: sealed`. Their frontmatter can be mentioned.
