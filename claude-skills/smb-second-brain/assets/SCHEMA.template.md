# Schema

> The contract for this vault. The agent reads this before writing any note.
> Humans own this file. Everything else the agent maintains.

## What this brain is for

<!-- One paragraph. What is in here, and who asks it questions. -->

## Questions it must answer

<!-- Five real questions. These justify every type below. If a type doesn't
     serve one of these, delete it. -->

1.
2.
3.
4.
5.

## Note types

| Type | Folder | One per… | Links to |
|---|---|---|---|
| `episode` | `episodes/` | source document | `concept`, `theme` |
| `concept` | `concepts/` | recurring idea | `theme`, back to `episode` |
| `theme` | `themes/` | top-level stage or category | `concept` |

<!-- 3–6 types. Singular type names, plural folders. Every type needs a
     link rule — if you can't name what it links to, it's a tag, not a type. -->

## Frontmatter

Every note:

```yaml
---
type: <one of the types above>
title: "Human-readable title"
summary: "One sentence. This is what shows in the index and on graph hover."
tags: [<vault-tag>, <type>]
---
```

Type-specific fields:

<!-- e.g. episode: guest, date, url, industry, buyer -->

## Conventions

- Filenames: kebab-case, stable. The filename is the link target.
- Links: `[[folder/note-name|Display text]]` — wikilinks only, never markdown
  links, or the graph and backlinks break.
- One H1 per note, matching `title`.
- Real UTF-8 in frontmatter. Never `—`-style escapes.
- Every note links to at least one other note. A note with no links is a bug.
- Contradictions get flagged inline, never silently resolved:
  `> ⚠ Conflicts with [[other-note]]: …`
- `sources/` is immutable. Read it, never edit it.

## Index

`index.md` carries one line per note: `- [[note]] — one-liner`.
This is the retrieval engine. Every ingest updates it. Lint verifies it.

## Atlas config

Read by `build_atlas.py` when building the graph site, and by
`init_obsidian.py` when colouring the Obsidian graph. Keeping both here is
what makes the two views look like one product.

```json atlas
{
  "title": "My Second Brain",
  "subtitle": "One line describing what this is.",
  "disclaimer": "AI summaries can be wrong — always check the source.",
  "types": ["episode", "concept", "theme"],
  "hubs": [],
  "private": ["sources", "transcripts"],
  "colors": {}
}
```

| Key | Effect |
|---|---|
| `types` | Order of filter chips, legend, and colour assignment |
| `hubs` | Frontmatter fields that become graph nodes with no note file |
| `private` | Folders never shipped to the browser |
| `colors` | `{"episode": "#e6b54e"}` to override the palette |
