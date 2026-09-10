# Designing the schema

The schema is the product. Everything else is mechanical.

## The one question that sets it

**"What will you ask this thing?"**

Not "what documents do you have." The questions determine the note types. A
pile of seller call recordings becomes a completely different vault depending
on whether the user asks *"what objections keep coming up"* (→ objection
notes) or *"what's the status of the Henderson deal"* (→ deal notes).

Ask it before you read a single document. If they cannot name five real
questions, build ten notes from a sample and ask again — people recognise
their questions faster than they can generate them.

## Shape

**3–6 types.** Under three and you have a folder. Over six and the LLM starts
guessing at filing time, which is exactly the failure mode you are eliminating.

**Two tiers.** Concrete notes (one per source: episode, deal, meeting,
contract) and abstract notes (one per recurring idea: concept, objection,
theme, risk). Concrete notes point at abstract ones. That shape is what makes
the graph legible instead of hairball — and it is what makes "show me
everything about earnouts" possible when no single document is about earnouts.

**One hub layer.** Flat attributes that group things — industry, geography,
stage, owner. These usually do not deserve their own written notes, so declare
them as `hubs` in the atlas config and the builder synthesises them as nodes
from frontmatter.

## Worked examples

**Podcast / interview archive** (the Acquiring Minds Atlas)
```
episode  →  concept  →  theme
   ↓
industry, buyer-profile          (hubs, from frontmatter)
```
95 episodes, 35 concepts, 7 stage playbooks, 7 insight digests, 16 industries,
3 buyer profiles → 163 nodes, ~2,000 links.

**Deal flow / acquisition search**
```
deal  →  broker  →  industry
  ↓
diligence-finding  →  risk-pattern
```
Ask: "what did every seller say about customer concentration?"

**Company operations / onboarding**
```
process  →  system  →  team
   ↓
decision  →  principle
```
Ask: "why do we do it this way?" — the decisions are the part that walks out
the door when someone leaves.

**Customer research**
```
interview  →  pain-point  →  segment
    ↓
feature-request  →  theme
```
Ask: "which pain shows up across segments?"

## Rules of thumb

- **Name types as singular nouns.** `episode`, not `episodes` or
  `episode-notes`. Folders are plural, types are singular.
- **Every type needs a link rule.** If you cannot say what a type links to,
  it is not a type — it is a tag.
- **Kebab-case filenames**, and the filename is the link target. Stable
  filenames matter more than pretty ones; renaming breaks links.
- **Frontmatter for facts, body for prose.** Anything you might filter or
  group by goes in frontmatter.
- **Resist the sixth type.** When a document does not fit, the answer is
  usually a new *field*, not a new *type*.

## Iterating

Build 10 notes. Show the user two real ones plus the arrow sketch. Ask "what's
wrong with this?" Expect two or three rounds. Signals you got it right:

- Filing a new document is obvious, not a judgement call
- The user can predict which note answers a given question
- Abstract notes each have 5+ inbound links (under 3 → merge them)
- No type holds more than ~60% of all notes
