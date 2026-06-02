# ROADMAP Row Content Template

The full markdown body written into a ROADMAP row's `Content` field. One per project. Updated only when scope, milestones, or "what we're building" shifts — NOT on every distill.

## File structure

```markdown
# {Project Name} — Roadmap

_Last updated: {YYYY-MM-DD}_

## The Goal
{1–3 sentences: what is this project for? What does done look like?}

## Active Phase
{The current chunk of work. 1–2 sentences. This is what STATE's Current Focus is in service of.}

## Milestones
- [x] {Done milestone}
- [x] {Done milestone}
- [ ] {Current milestone}
- [ ] {Next milestone}
- [ ] {Future milestone}

## Out of scope
- {Things that have been explicitly decided NOT to do, but might be tempting}
- {Empty if nothing}

## Notes
{Optional. Long-arc context that doesn't fit elsewhere — why the project exists, who it's for, what success looks like.}
```

## Writing rules

- **The Goal** is the north star. It rarely changes. If it changes, the project might have become a different project.
- **Active Phase** is the current chunk. Updated when phases transition. "Phase 1: Build MVP" → "Phase 2: Get to 10 users."
- **Milestones** use checkboxes. Mark `[x]` when done. Don't delete completed ones — they're the project's history.
- **Out of scope** is the firewall against scope creep. Things explicitly punted go here.
- **Notes** is freeform. Use for context that doesn't fit the other sections.

## When to update ROADMAP

UPDATE if any of these happened in the chat:
- A new milestone got added or completed
- The Active Phase shifted
- Something got punted out of scope
- The Goal got refined

DON'T update if:
- You just made progress on the active milestone (that goes in STATE)
- You made a decision (that goes in DECISIONS)
- You generated an artifact (that goes in ARTIFACT)

## Anti-patterns

- Don't put session-level updates here. ROADMAP is months. STATE is days.
- Don't list every task as a milestone. Milestones are chunks worth celebrating.
- Don't write the Roadmap in the first chat unless the user clearly articulates one. Better to leave ROADMAP empty than fabricate a roadmap.
