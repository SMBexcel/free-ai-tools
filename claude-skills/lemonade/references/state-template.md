# STATE Row Content Template

The full markdown body written into a STATE row's `Content` field. One per project. Overwritten on every `distill`.

```markdown
# {Project Name} — State

_Last distilled: {ISO date} from chat: {chat title or "untitled"}_

## Current Focus
{1–3 sentences on what's actively being worked on right now. Not what we COULD do — what we ARE doing.}

## Last Session Summary
- {bullet, 1 line each}
- {3–5 bullets total}
- {what happened, what got decided, what got built}

## Next Moves
- {1–5 concrete things to do next, in priority order}
- {the top one is what rehydrate should suggest starting with}

## Open Questions
- {unresolved items needing user input or more thought}
- {leave empty section if none}

## Suggested Next Step
{1–2 sentences inferring the next concrete action. Usually the top item from Next Moves, but written in active voice as if directing the next chat.}
```

## Writing rules

- **Current Focus** is the present moment. "Working on the pricing table layout." Not "could build a pricing table."
- **Last Session Summary** describes the chat being distilled, not all-time history. 3–5 bullets max.
- **Next Moves** is ordered — top is highest priority. Keep to 5 max. If there are more, the rest belong in DECISIONS or just in your head.
- **Open Questions** is for things you can't proceed on without more info or a decision from the user. Empty is fine.
- **Suggested Next Step** is what the next chat's rehydrate will surface most prominently. Make it actionable: "Start on the CTA copy variants" not "consider next steps."

## Anti-patterns

- Don't dump the whole chat into Last Session Summary. 5 bullets max.
- Don't put decisions in STATE. They go in DECISIONS.
- Don't put roadmap-level stuff in STATE. STATE is *now*. ROADMAP is *the arc*.
- Don't put todos as a separate section — Next Moves IS the todo list for this skill's purposes.
