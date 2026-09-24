# Obsidian compliance

Every vault this skill writes must open in Obsidian (https://obsidian.md) with
zero conversion. Obsidian is free, local, cross-platform, and ships a graph
view — it is the fastest way for someone to *see* their second brain, and it
is the fallback when they do not want to run the build script at all.

Obsidian is a reader over plain folders. There is no import, no database, no
lock-in: "Open folder as vault" and it works. The `.obsidian/` folder holds
per-vault settings and nothing else — delete it and you still have your notes.

## Hard rules

**1. Wikilinks, not markdown links, between notes.**
```
[[episodes/2024-03-14-jane-doe|Jane Doe on seller financing]]   ✓
[Jane](./episodes/2024-03-14-jane-doe.md)                       ✗
```
Both render, but only wikilinks populate the graph view and backlinks pane.
Use standard markdown links for external URLs.

**2. Filenames are link targets.** Kebab-case, no extension in the link.
Never use `\ / : * ? " < > |` — illegal on some platforms and they break
links. Keep them stable; a rename breaks every inbound link unless Obsidian
does it for you.

**3. YAML frontmatter, valid.** Obsidian's Properties panel parses it and will
show a parse error to the user if it is malformed.
```yaml
---
type: episode
title: "Jane Doe on seller financing"
tags: [podcast, episode]
industry: construction-trades
---
```
- Quote any value containing `:` `#` `[` `]` or starting with a special char.
- **Write real UTF-8, never escaped.** Emit `—` itself, not the
  six-character escape `\u2014`. Building notes by `json.dumps`-ing a string
  into YAML produces the escape, and it renders as garbage in both Obsidian
  and the atlas. This is the single most common way a generated vault ends up
  looking broken, and it is invisible until someone opens it.
- `tags` must be a list, and tag values cannot contain spaces.

**4. One H1 per note, matching the title.** Obsidian's outline and the atlas
builder both key off it.

**5. Attachments in one folder.** Set `attachmentFolderPath` in
`.obsidian/app.json` (this skill points it at `sources/`).

## Setup

```bash
python3 scripts/init_obsidian.py --vault ./my-brain
```

Writes `.obsidian/` with core plugins on (graph, backlinks, outgoing links,
tag pane, properties, outline) and one graph colour group per note type,
using the same palette as `build_atlas.py`. The Obsidian graph and the
atlas site then look like the same product.

Re-running is safe: only `graph.json` is rewritten, so a user's own settings
survive. Pass `--force` to overwrite everything.

Then: Obsidian → **Open folder as vault** → pick the vault folder.

## Obsidian vs. the atlas site

Ship both. They are different jobs.

| | Obsidian | Atlas site |
|---|---|---|
| Setup | Install an app, open a folder | Run a script, serve a folder |
| Audience | The owner | The owner, on their machine |
| Editing | Yes | No — read only |
| Graph | 2D, built in, filterable | 3D, styled, embeddable |
| Search | Full-text over everything | Index + type filters |
| Backlinks | Automatic panel | "Linked notes" list |
| Offline | Yes | Yes |
| Cost | Free | Free, runs locally |

Rule of thumb: **Obsidian is the workshop, the atlas is the showroom.** The
user works in Obsidian daily; they render the atlas when they want to see
the whole map at once.

## Gotchas

- **`.obsidian/workspace.json`** records open panes and changes constantly.
  Gitignore it, and never ship it in a distributed vault.
- **Unresolved links** show as faded nodes in the graph. That is a feature —
  they mark notes worth writing. `build_atlas.py` reports them as
  "unresolved wikilink targets"; treat a spike as a LINT finding.
- **Orphans** are hidden in the graph unless `showOrphans` is on. This skill
  leaves it on so the user sees their own filing gaps.
- **Nested tags** (`#deal/closed`) work and are worth using for hierarchy.
