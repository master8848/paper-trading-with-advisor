# Agent Notes — README

Agent Notes record rationale and decisions for non-trivial changes. Reference pages under `docs/` record current behavior; notes record why.

## Format

Each note lives at `.agents/notes/implemented/{class}/YYYY-MM-DD-slug.md` and uses the uniform header.

The header is exactly `# Agent Note: <title>` on line 1, a blank line on line 2, and `Status: implemented` on line 3. No variations.

Body sections after the header: `## Context`, `## Decision`, `## Consequences`. Each paragraph is one physical line.

## Template

```
# Agent Note: concise imperative title

Status: implemented

## Context

One line stating the current state and constraint that prompted the change.

## Decision

One line stating what was chosen, naming exact files, crates, or flags.

## Consequences

One line stating the resulting current behavior or follow-up location.
```

Copy the template verbatim. Replace the title and body lines; keep the header spacing and `Status: implemented` literal.

## Classification

`{class}` is one of: `architecture`, `optimization`, `correctness`, `tooling`, `docs`, `self-hosted`.

Use `architecture` for structural or crate-level choices; `optimization` for performance changes; `correctness` for bug fixes; `tooling` for build/CI/dev tooling; `docs` for doc-structure changes; `self-hosted` for operator knobs.

Match existing precedent under `.agents/notes/implemented/` when choosing a class. If no precedent fits, use `architecture` and note the rationale in `## Context`.

## Lifecycle

Non-trivial changes carry an Agent Note in the same change. Do not defer notes to a follow-up.

A worklog converts into a note: create the note at `.agents/notes/implemented/{class}/YYYY-MM-DD-slug.md` with uniform format, then delete the worklog.

Implemented notes are append-only. Do not edit the header after merging; supersede with a new note that links to the prior one.

*Word budget: ≤ 500 words. Verify with `wc -w .agents/notes/README.md`.*
