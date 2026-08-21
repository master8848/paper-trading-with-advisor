# AGENTS.md — Documentation Contract

This file is the standing contract for all documentation under `docs/` and Agent Notes under `.agents/notes/`. Read it before editing any documentation.

## Tier Taxonomy

Tier 1 — Standing rules: `docs/AGENTS.md` (this file). Defines writing rules, budgets, and slop criteria for all docs.

Tier 2 — Reference pages: `docs/wasm.md`, `docs/optimization-notes.md`, and other `docs/*.md` lookup pages. Each page documents current behavior and scope for its area.

Tier 3 — Agent Notes: `.agents/notes/implemented/{class}/YYYY-MM-DD-slug.md`. Each note records rationale and decisions for a non-trivial change.

Tier 4 — Operator knobs: `self-hosted/advanced/knobs.md` (or equivalent). Documents env vars, flags, and deployment knobs.

One home per fact. Rationale → Tier 3; current behavior → Tier 2; knobs → Tier 4; standing rules → Tier 1. Elsewhere, link to the home.

## Writing Rules

Describe current state, not history. Do not narrate prior states, incremental edits, or migration steps.

One physical line per paragraph. Each paragraph is exactly one newline-terminated line; a blank line separates paragraphs.

Use concrete prose. Name exact crates, file paths, env vars, flags, and commands. No metaphors, analogies, or vague placeholders.

No reasoning transcripts or worklog narration in final docs. Worklogs convert into Agent Notes (see `.agents/notes/README.md`).

Link instead of duplicating. If a fact's home is elsewhere, add a relative link with a verified `#fragment`.

Classify the document as reference or tutorial. These docs are references (lookup scope, current behavior). Do not add tutorial walkthroughs to reference pages.

## Word Budgets

`docs/AGENTS.md` ≤ 1,000 words; `docs/wasm.md` ≤ 1,800 words; `docs/optimization-notes.md` ≤ 2,000 words; `.agents/notes/README.md` ≤ 500 words.

Enforcement: `wc -w <file>` on the markdown source excluding YAML frontmatter must not exceed the limit. CI or pre-submit checks should fail the change if any touched file exceeds its budget.

If over budget: relocate content to its fact's home → condense to current-state concrete prose → raise with justification in the Agent Note if still over. Do not silently exceed the budget.

Current word count of this file: ~310 words (well under the 1,000-word limit; verify with `wc -w docs/AGENTS.md` before submitting edits).

## Slop Checklist

Audit every docs change against this checklist; fix violations before submitting.

Duplicated facts: the same fact appears in more than one home. Fix: keep one home, link elsewhere.

Narrated history: prose describes how the docs or code evolved rather than current behavior. Fix: rewrite to current state.

Status annotations: inline markers like `TODO`, `FIXME`, `WIP`, or `deprecated` without a linked home. Fix: remove or link to the tracking issue or Agent Note.

Hand-restated source: prose repeats what the linked source file already states verbatim. Fix: link to the source.

Emphasis inflation: excessive bold, italics, caps, or exclamation that adds no information. Fix: use plain concrete prose.

Paragraph walls: multiple sentences joined into a single paragraph or paragraphs spanning multiple physical lines. Fix: split to one line per paragraph.

## Verification

Every relative link must resolve: target file exists on disk and any `#fragment` matches the slugified heading (`lowercase`, strip punctuation, spaces → `-`).

Word budgets must hold for all touched files.

Agent Notes must use the exact header `# Agent Note: <title>`, blank line, `Status: implemented` (see `.agents/notes/README.md`).

*Word budget: ≤ 1,000 words. Verify with `wc -w docs/AGENTS.md`.*
