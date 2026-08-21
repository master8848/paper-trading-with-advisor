---
name: dsh-doc-standards
description: Guidance for editing docs — tier taxonomy, writing rules, word budgets, slop checks, and Agent Note lifecycle for reference documentation.
---

# dsh-doc-standards

Guidance, not a script. The contract lives in `docs/AGENTS.md` and `.agents/notes/README.md`; read both before editing any documentation.

## When to Use

Use this skill when creating or editing any documentation under `docs/`, when adding or modifying Agent Notes under `.agents/notes/`, or when moving facts between docs and notes.

Use this skill when reviewing docs for style, budget, or link correctness, or when converting a worklog into an Agent Note.

Do not use for code-only changes with no docs impact.

## Sources of Truth

`docs/AGENTS.md` defines tier taxonomy, writing rules, word budgets, and the slop checklist.

`.agents/notes/README.md` defines Agent Note format, classification, and lifecycle.

Existing Agent Notes under `.agents/notes/implemented/` establish precedent for uniform note format; match their structure exactly.

## Workflow

1. Locate the fact's home first. One home per fact: rationale and decisions → `.agents/notes/implemented/{class}/YYYY-MM-DD-slug.md`; current behavior and lookup reference → `docs/` reference pages; operator env vars and knobs → `self-hosted/advanced/knobs.md` (or equivalent per `docs/AGENTS.md`); standing rules → `docs/AGENTS.md`. Elsewhere, link there.

2. Classify the document as reference or tutorial. These docs are references (lookup scope, current behavior). Do not add tutorial narration, walkthroughs, or worklog transcripts to reference pages.

3. Apply the writing rules: describe current state, not history; one physical line per paragraph (one newline-terminated line per paragraph, no hard-wrapped continuations); concrete prose with exact crates, files, env vars, flags, and paths — no metaphors or vague placeholders; no reasoning transcripts or worklog narration.

4. Non-trivial changes carry an Agent Note in the same change. A worklog converts into one at `.agents/notes/implemented/{class}/YYYY-MM-DD-slug.md` with uniform format, then delete the worklog.

5. Audit the slop checklist from `docs/AGENTS.md`: duplicated facts, narrated history, status annotations, hand-restated source, emphasis inflation, paragraph walls.

6. Verify mechanically before submitting: every relative link resolves (target file exists, `#fragment` matches a heading slug), word budgets hold, note header is exactly `# Agent Note: <title>` followed by a blank line followed by `Status: implemented`.

## Writing Rules

Write current behavior, not change history. Do not narrate previous states, migrations, or incremental edits.

One physical line per paragraph. A blank line separates paragraphs; each paragraph occupies exactly one line in the source file.

Use concrete prose: name the exact crate, file path, env var, flag, or command. Avoid metaphors, analogies, and generic placeholders.

No reasoning transcripts, worklog narration, or internal monologue in final docs.

Link to the fact's home instead of duplicating it. If the fact lives elsewhere, add a relative link.

## Budgets

`docs/AGENTS.md` ≤ 1,000 words; `docs/wasm.md` ≤ 1,800 words; `docs/optimization-notes.md` ≤ 2,000 words; `.agents/notes/README.md` ≤ 500 words.

If over budget: relocate content to its fact's home → condense to current-state prose → raise with justification in the Agent Note if still over.

Word count is checked mechanically (`wc -w` on the rendered markdown source, excluding frontmatter). Keep a margin of at least 10% under the limit when adding new sections.

## Agent Note Lifecycle

Classification under `.agents/notes/implemented/{class}/` uses the classes defined in `.agents/notes/README.md`.

An Agent Note is created in the same change as the docs edit it documents. Do not defer or batch notes across changes.

Convert worklogs by moving rationale and decisions into the uniform note format at `.agents/notes/implemented/{class}/YYYY-MM-DD-slug.md`, then delete the worklog file.

## Verification Checklist

- [ ] Read `docs/AGENTS.md` and `.agents/notes/README.md` before editing.

- [ ] Each new or moved fact has exactly one home; all other locations link there.

- [ ] Document classified as reference (no tutorial narration).

- [ ] Writing rules applied: current state, one line per paragraph, concrete paths/vars/flags, no transcripts.

- [ ] Slop checklist audited: no duplicated facts, narrated history, status annotations, hand-restated source, emphasis inflation, or paragraph walls.

- [ ] Every relative link resolves: `target.md` exists on disk and `#fragment` matches the slugified heading (`lowercase`, `a-z0-9-`, spaces → `-`).

- [ ] Word budgets hold for all touched files (`docs/AGENTS.md`, `docs/wasm.md`, `docs/optimization-notes.md`, `.agents/notes/README.md`).

- [ ] Agent Note (if required) at `.agents/notes/implemented/{class}/YYYY-MM-DD-slug.md` with header exactly `# Agent Note: <title>`, blank line, `Status: implemented`, and uniform body; worklog deleted if converted.

- [ ] No history narration or status annotations remain in reference pages.
