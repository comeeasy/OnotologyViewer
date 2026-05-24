# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Coding Principles

These four principles apply to every task in this codebase:

### 1. Think Before Coding
Ask for clarification if a prompt is ambiguous. Surface trade-offs and stop to identify what is unclear rather than silently guessing a solution. Never start coding when the intent or constraints are still in question.

### 2. Simplicity First
Implement the absolute minimum code required to solve the problem. Do not add speculative abstractions, "flexibility," or over-engineer features that were not requested.

### 3. Surgical Changes
Only touch the files and functions directly related to the task. Do not refactor unrelated neighboring code or "improve" things that are not broken.

### 4. Goal-Driven Execution
Turn vague instructions into verifiable success criteria before writing any code. Define clear tests or outcomes so the work can be verified.


## LLM Wiki Schema

This project uses the **LLM Wiki pattern**: you maintain a persistent, compounding wiki in `wiki/` fed by raw sources in `raw/`. You write and maintain all wiki files. The user reads; you write.

---

### Directory Layout

```
raw/          ← immutable source documents (never modify)
wiki/
  index.md    ← catalog of all pages (always update after any change)
  log.md      ← append-only chronological log (always append after any operation)
  concepts/   ← one .md per ontology/KG concept
  entities/   ← one .md per named entity (person, tool, project, org)
  sources/    ← one .md per ingested source document
  queries/    ← saved query results and analyses (create as needed)
```

---

### Page Formats

#### Concept page (`wiki/concepts/<slug>.md`)
```markdown
# <Concept Name>

**Category:** [Ontology Language | Reasoning | Data Model | Query | Standard | Other]  
**Related:** [[concept-a]], [[concept-b]]  
**Sources:** [[source-slug-1]], [[source-slug-2]]

## Definition
<1–3 sentence definition>

## Key Points
- ...

## Relationships to Other Concepts
- **vs [[related-concept]]:** ...

## Notes & Contradictions
- ...
```

#### Entity page (`wiki/entities/<slug>.md`)
```markdown
# <Entity Name>

**Type:** [Person | Tool | Project | Organization | Dataset | Standard]  
**Related concepts:** [[concept-a]]  
**Sources:** [[source-slug]]

## Overview
<brief description>

## Significance
<why this entity matters in the domain>

## Notes
- ...
```

#### Source summary page (`wiki/sources/<slug>.md`)
```markdown
# <Title>

**Type:** [Paper | Article | Book Chapter | Blog | Other]  
**Author(s):** ...  
**Date:** YYYY-MM  
**Original file:** `raw/<filename>`  
**Concepts covered:** [[concept-a]], [[concept-b]]  
**Entities mentioned:** [[entity-a]]

## Summary
<2–5 sentence summary of the source>

## Key Takeaways
- ...

## Contradictions / Open Questions
- ...
```

#### Query result page (`wiki/queries/<slug>.md`)
```markdown
# <Question or Analysis Title>

**Date:** YYYY-MM-DD  
**Sources used:** [[source-a]], [[concept-b]]

## Answer / Analysis
...

## Supporting Evidence
...
```

---

### Operations

#### INGEST — when the user says "이 파일 수집해" / "ingest this"
1. Read the source file in `raw/`.
2. Discuss key takeaways with the user briefly if needed.
3. Create `wiki/sources/<slug>.md` with the source summary format above.
4. Create or update `wiki/concepts/<slug>.md` for every concept mentioned.
5. Create or update `wiki/entities/<slug>.md` for every named entity.
6. Update `wiki/index.md`: add/update rows in the relevant tables, increment counters.
7. Append to `wiki/log.md`:
   ```
   ## [YYYY-MM-DD] ingest | <Source Title>
   - Pages created: ...
   - Pages updated: ...
   ```

#### QUERY — when the user asks a question about the wiki
1. Read `wiki/index.md` first to find relevant pages.
2. Read the relevant pages.
3. Synthesize and answer with citations (e.g., `[[concept-a]]`, `[[source-b]]`).
4. If the answer is non-trivial and reusable, ask: "이 답변을 위키에 저장할까요?"
5. If yes, create `wiki/queries/<slug>.md` and update index + log.
6. Append to `wiki/log.md`:
   ```
   ## [YYYY-MM-DD] query | <Question summary>
   - Pages read: ...
   - Result saved: wiki/queries/<slug>.md (or "not saved")
   ```

#### LINT — when the user says "위키 점검해" / "lint the wiki"
Check for and report:
- Pages with no inbound links (orphans)
- Concepts mentioned in text but lacking their own page
- Contradictions between pages
- Stale claims (newer sources supersede older ones)
- Missing cross-references between obviously related pages
- Suggested new topics to investigate

Append to log:
```
## [YYYY-MM-DD] lint | Health check
- Issues found: ...
- Actions taken: ...
```

---

### Conventions
- **Slugs:** lowercase, hyphens, English (e.g., `owl-ontology`, `knowledge-graph`)
- **Cross-links:** use `[[slug]]` format for all internal references
- **Language:** keep original source language in quotes/excerpts; wiki prose can be Korean or English per user preference
- **Never modify** files in `raw/`
- **Always update** `wiki/index.md` and append to `wiki/log.md` after every operation
- **One page per concept** — update existing pages rather than creating duplicates
