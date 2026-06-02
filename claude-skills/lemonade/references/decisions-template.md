# DECISIONS / Learnings Row Content Template

The full markdown body written into a DECISIONS row's `Content` field. One per project (or one for `__global__`). **Append-only** — new entries go at the TOP (reverse chronological), old entries are never deleted.

In **project mode**, this row is a KDD (Key Decision Document) log — decisions worth remembering.
In **global mode** (Project = `__global__`), this row is a general learnings log — cross-chat insights, patterns, and heuristics.

The template below works for both; section labels stay the same but the bar for what to log differs (see SKILL.md "decision-worthiness" vs "learning-worthiness").

## File structure

```markdown
# {Project Name} — Decisions Log

_Reverse chronological. Newest first._

---

## {YYYY-MM-DD} · {Short decision title}

**Decision:** {one sentence}

**Rationale:** {why this over the alternatives}

**Alternatives considered:** {what was rejected and briefly why}

**Reversibility:** {One-way door | Two-way door}

**Context:** {optional 1–2 sentences on what triggered the decision}

---

## {YYYY-MM-DD} · {Next older decision...}

...
```

## Writing rules

- **Order**: newest at the top, older entries below. Append by *prepending* — read existing Content, add new section between the header and the first existing `---`, rewrite.
- **Date format**: ISO `YYYY-MM-DD`. If multiple decisions on the same day, that's fine — they share a date header but each gets its own section.
- **Decision-worthiness bar**: Log if reversing would cost more than 10 minutes of work. Architectural choices, schema, library selection, naming conventions, business logic. Skip casual choices ("let's use 3 columns here").
- **Reversibility**:
  - *One-way door* — undoing this would be expensive (renaming a public API, choosing a DB engine, picking a brand name)
  - *Two-way door* — easy to reverse (component layout, copy variants, internal helper names)
- **Title**: 3–7 words. "Use Notion as memory substrate" not "We decided to use Notion".

## Rotation

When the row's Content exceeds **40,000 characters**, the skill splits it (see SKILL.md "Rotation & limits"). The older half moves to an `ARTIFACT` row named `decisions-archive-<YYYY-MM>`. The DECISIONS row keeps only the newer half plus new entries. Do not manually edit rotated archives — they're an append-only audit trail.

## Anti-patterns

- Don't log every choice. The log is for decisions you'd want to remember in 6 months.
- Don't bury the lede. The **Decision** line should be readable on its own.
- Don't merge multiple decisions into one entry. One decision per section, even if related.
- Don't delete old entries. If a decision was reversed, log the reversal as a NEW entry that references the old one.
