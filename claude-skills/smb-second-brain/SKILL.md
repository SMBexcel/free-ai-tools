---
name: smb-second-brain
description: Turn a pile of unstructured documents into an AI second brain — an LLM-maintained wiki of linked markdown notes you can ask questions and explore as a 3D knowledge graph. Use this skill when the user has a folder of transcripts, contracts, notes, PDFs, CIMs, research, or meeting recordings and wants to make it queryable; when they say "build me a second brain", "make my docs searchable", "turn this folder into a wiki", "set up an LLM wiki", "Karpathy wiki", "knowledge graph from my documents"; or when they want to publish an existing vault as a browsable graph site. Covers all five operations — SETUP (design the schema), INGEST (file new docs), QUERY (ask with citations), LINT (health-check the wiki), and PUBLISH (build the graph site). No database, no embeddings, no code required from the user.
---

# Second Brain — build an LLM wiki from a pile of docs

This skill implements the **Karpathy LLM-wiki model**: you curate raw
sources, the LLM maintains a wiki of linked markdown notes over them, and a
schema file keeps it disciplined. Then any model — including a cheap fast one
— answers hard questions by following the map instead of re-reading
everything.

Read `references/karpathy-model.md` before your first SETUP so you are
implementing the actual architecture rather than "making some notes".

## The five operations

| Op | When | What you do |
|---|---|---|
| **SETUP** | First run | Sample the docs, propose a schema, iterate with the user |
| **INGEST** | New docs arrive | Write/update notes, cross-link into the existing graph |
| **QUERY** | User asks a question | Index → entry node → traverse → answer with citations |
| **LINT** | Every ~20 ingests | Contradictions, orphans, stale claims, missing cross-refs |
| **PUBLISH** | They want to show it | Build `atlas.json`, serve the graph site |

Announce which operation you are running. Never silently switch.

---

## The three layers (never blur them)

```
1. RAW SOURCES   /sources/     immutable. LLM reads, NEVER edits. Never shipped to a browser.
2. THE WIKI      /<types>/     LLM-generated linked markdown. The agent owns this.
3. THE SCHEMA    SCHEMA.md     types, link rules, conventions. The user owns this.
```

Layer 3 is the whole product. A vault with a weak schema is a folder of notes.
A vault with a good schema is a second brain.

---

## SETUP — design the schema first

**Do not ingest the whole pile first.** Schema before volume, every time. A
bad schema found at doc 400 costs a rebuild; found at doc 10 it costs a
minute.

1. **Inventory.** Count files by type/extension. Report it. Ask what the
   pile *is* and — the important question — **what they intend to ask it.**
   The questions determine the schema, not the documents.
2. **Sample.** Read 5–10 documents spread across the pile. Never all of them.
3. **Propose a schema.** 3–6 note types and the links between them. Show it
   as an arrow sketch: `deal → broker → industry`. Explain each type in one
   line. See `references/schema-design.md` for the patterns and the worked
   examples.
4. **Iterate.** Build ~10 real notes from the sample. Show the user two
   actual notes and the arrow sketch. Ask what is wrong. Expect 2–3 rounds —
   that is the process working, not failing.
5. **Freeze it.** Write `SCHEMA.md` from `assets/SCHEMA.template.md`, filled
   in. Only then ingest the rest.

**Scaffold:**

```
my-brain/
├─ .obsidian/         Obsidian settings (written by scripts/init_obsidian.py)
├─ SCHEMA.md          the contract (types, links, conventions, atlas config)
├─ index.md           one line per note — this is the retrieval engine
├─ sources/           raw docs, read-only, never shipped
└─ <type>/            one folder per note type
```

Then make it open in Obsidian — do this at SETUP, not at PUBLISH, so the user
can watch their graph fill in as you ingest:

```bash
python3 ~/.claude/skills/smb-second-brain/scripts/init_obsidian.py --vault ./my-brain
```

(Adjust the path if the skill is installed project-scoped. On Windows use
`py -3`. If the user has no Python, skip this — the vault still opens in
Obsidian, it just won't be colour-coded per type.)

## INGEST — file a document into the wiki

Per document:

1. Read it. Decide its type from `SCHEMA.md`. If it fits nothing, **stop and
   ask** — do not invent a type mid-run.
2. Write the note: frontmatter (`type`, `title`, `summary`, plus the schema's
   fields), then the body.
3. **Link it.** `[[wikilinks]]` to every note it relates to. Links are the
   product — a note with no links is invisible to the graph.
4. **Update the neighbours.** This is the step people skip. A new note
   usually means editing 5–15 existing notes so the links go both ways.
5. Add one line to `index.md`.
6. Flag contradictions in a `> ⚠ Conflicts with [[other-note]]: …` blockquote
   rather than silently overwriting. Contradictions in the source are signal.

Ingest is expensive at scale — it touches many pages per doc. Batch it, warn
the user before a 500-doc run, and checkpoint so it can resume.

## QUERY — answer from the wiki

1. Read `index.md`. Pick the entry node from the one-liners.
2. Traverse the links out from there. Read whole notes, not fragments.
3. Answer, **citing the note for every claim**. Never answer from memory of
   the corpus.
4. If the answer was genuinely hard to assemble, offer to file it back as a
   new synthesis note. That is how the brain compounds.
5. If you could not find it, say so plainly and name what you searched. A
   confident wrong answer destroys the tool's value.

## LINT — keep it honest

Run every ~20 ingests, or on request:

- **Orphans** — notes with no links in or out
- **Dead links** — `[[targets]]` that resolve to nothing
- **Contradictions** — notes making incompatible claims
- **Stale** — notes whose source has changed
- **Index drift** — notes missing from `index.md`, or entries pointing nowhere
- **Type sprawl** — a type with 1–2 members usually wants merging

Report as a table with a recommended fix per row. Apply fixes only on the
user's say-so.

## Obsidian compliance — non-negotiable

Every vault you write must open in **Obsidian** (https://obsidian.md, free)
with zero conversion. It is the user's daily driver and their zero-setup way
to see the graph. Full rules in `references/obsidian.md`; the four that break
things:

1. **Wikilinks between notes**, never markdown links —
   `[[episodes/foo|Title]]`. Markdown links render but populate neither the
   graph view nor the backlinks pane.
2. **Valid YAML frontmatter**, with real UTF-8. Never emit `\u2014`-style
   escapes; they render as garbage in Obsidian and in the atlas.
3. **Kebab-case filenames**, no `\ / : * ? " < > |`, and stable — a rename
   breaks every inbound link.
4. **One H1 per note**, matching the frontmatter `title`.

Obsidian is the workshop, the atlas site is the showroom. Ship both.

## PUBLISH — build the graph site

There are two ways to see the brain, and the user should have both.

**Option 1 — Obsidian (no build).** The vault is already a valid Obsidian
vault. Open folder as vault → the graph view is right there, colour-coded per
type by `init_obsidian.py`, with backlinks and full-text search. This is the
answer for a user who does not want to run anything.

**Option 2 — the atlas site (shareable).**
`scripts/build_atlas.py` reads the vault and emits one `atlas.json`.
`assets/site/` is a static viewer for it: editorial index on the left, 3D
force-directed graph on the right, click a node to read the note, wikilinks
navigate. Zero build step, zero dependencies, works offline.

**Paths below are relative to this skill's own directory, not the user's
project.** Resolve them against wherever this skill is installed — typically
`~/.claude/skills/smb-second-brain/` or `<project>/.claude/skills/smb-second-brain/`.
Substitute the real absolute path when you run these; do not paste them as-is:

```bash
SKILL=~/.claude/skills/smb-second-brain          # adjust if project-scoped

cp -R $SKILL/assets/site ./site
python3 $SKILL/scripts/build_atlas.py --vault ./my-brain --out ./site/data/atlas.json
cd site && python3 -m http.server 4355     # http://localhost:4355
```

On Windows, `python3` is usually `py -3`. If neither resolves, the user needs
Python from python.org — say so rather than letting the command fail twice.
Python is only needed to publish; SETUP, INGEST, QUERY and LINT need none.

`file://` will not work — the viewer fetches `atlas.json`, so it needs a
server. Any static host will do (Cloudflare Pages, Netlify, GitHub Pages):
upload the `site/` folder, no build command.

The builder is config-free by default and infers everything from the vault.
`SCHEMA.md`'s ```json atlas``` block tunes it:

| Key | Effect |
|---|---|
| `title` / `subtitle` / `disclaimer` | Page copy |
| `types` | Type order → chip order, legend order, colour assignment |
| `colors` | `{"episode": "#e6b54e"}` to override the palette |
| `hubs` | Frontmatter fields that become nodes (`industry`, `buyer`) even with no note file |
| `private` | Folders never shipped to the browser |

`private` defaults to `transcripts, raw, sources, source, archive, pipeline`
— raw sources stay out of `atlas.json` unless the user opts in. Say so when
you publish. Use `--no-bodies` for a graph with no note text at all.

Read `references/atlas-ui.md` to customise the viewer.

---

## Rules

- **Schema before volume.** Always.
- **Never edit `sources/`.** Raw layer is immutable.
- **A note with no links is a bug.**
- **Cite everything.** Every claim traces to a note; every note traces to a source.
- **Let the failure justify the complexity.** No embeddings, no graph
  database, no chunking until the plain wiki visibly misses answers the user
  knows are in there. That is usually never. If it does happen, the upgrade
  path is in `references/karpathy-model.md`.
- **AI summaries can be wrong.** Keep the disclaimer on any published site,
  and keep a link back to the real source on every note.
