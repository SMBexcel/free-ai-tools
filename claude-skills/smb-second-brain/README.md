# Second Brain

**Version 1.0**

Turn a folder of documents into an AI second brain: an LLM-maintained wiki of
linked markdown notes you can ask questions, open in Obsidian, and publish as
a 3D knowledge graph.

No database. No embeddings. No code you have to write. The "database" is a
folder of markdown files.

It implements Andrej Karpathy's
[LLM-wiki model](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f):
you curate raw sources, the LLM maintains a wiki over them, and a schema file
keeps it disciplined.

---

## Requirements

| | |
|---|---|
| **[Claude Code](https://claude.com/claude-code)** | Required. This is a Claude Code skill — the LLM does the reading, filing, and linking. |
| **Python 3.8+** | Required only to publish the graph site. Standard library only, nothing to `pip install`. Pre-installed on macOS and most Linux. On Windows, install from [python.org](https://python.org) and use `py -3` wherever this README says `python3`. |
| **[Obsidian](https://obsidian.md)** | Optional but recommended. Free. The easiest way to see and edit your brain. |

You do **not** need: a database, an embeddings provider, an API key beyond
Claude Code itself, Node, or any build tooling.

## Install

Drop this folder into one of two places:

```bash
# Available in every project
mkdir -p ~/.claude/skills && cp -R smb-second-brain ~/.claude/skills/

# Or scoped to a single project
mkdir -p .claude/skills && cp -R smb-second-brain .claude/skills/
```

Restart Claude Code. Confirm it registered by asking Claude to list your
skills, or just start with the quickstart below — it triggers on plain
language.

## Quickstart

Point Claude Code at a folder of documents and say what you want:

```
I have a folder of ~200 seller call transcripts in ./calls.
Build me a second brain from them.
```

Claude will run **SETUP**: inventory the pile, ask what questions you want
answered, read a sample of ~10 docs, propose a schema, and iterate with you
until filing a new document is obvious rather than a judgment call. Expect two
or three rounds — that step is the whole game, and rushing it is the one
expensive mistake.

Once the schema is frozen, it ingests the rest and you start asking.

## What you end up with

```
my-brain/
├─ .obsidian/       Obsidian settings, graph colour-coded per note type
├─ SCHEMA.md        the contract: note types, link rules, conventions
├─ index.md         one line per note — this is the retrieval engine
├─ sources/         your raw docs, read-only, never published
└─ <type>/          one folder per note type, full of linked markdown
```

Every note is plain markdown with YAML frontmatter and `[[wikilinks]]`. No
lock-in: it is a folder, and it stays a folder.

## Two ways to see it

**Obsidian — no build.** Your vault is already a valid Obsidian vault.
*Open folder as vault* and you get the graph view, backlinks, and full-text
search immediately. This is where you work day to day.

**The atlas site — shareable.** One script turns the same vault into a static
site: editorial index on the left, 3D graph on the right, click a node to read
the note.

```bash
cp -R ~/.claude/skills/smb-second-brain/assets/site ./site
python3 ~/.claude/skills/smb-second-brain/scripts/build_atlas.py \
        --vault ./my-brain --out ./site/data/atlas.json
cd site && python3 -m http.server 4355        # then open http://localhost:4355
```

`file://` will not work — the page fetches `atlas.json`, so it needs a server.
Any static host works for deploying (Cloudflare Pages, Netlify, GitHub Pages):
upload `site/`, no build command.

Obsidian is the workshop. The atlas is the showroom. Same vault behind both.

## The five operations

| Op | When |
|---|---|
| **SETUP** | First run — design the schema |
| **INGEST** | New docs arrive — file them and update their neighbours |
| **QUERY** | Ask a question — answered with citations |
| **LINT** | Every ~20 ingests — orphans, dead links, contradictions, drift |
| **PUBLISH** | Build the graph site |

Just say what you want ("add these 30 new transcripts", "lint the vault",
"what did sellers say about customer concentration?") and Claude picks the
operation.

## Privacy

`build_atlas.py` refuses to publish your raw sources by default. Folders named
`sources`, `transcripts`, `raw`, `source`, `archive`, and `pipeline` are
withheld from `atlas.json`, and the build prints which ones it withheld.
Override with `private` in `SCHEMA.md`. For a graph with no note text at all,
use `--no-bodies`.

Check before you deploy. `atlas.json` is a single file served to every visitor.

## Layout

```
smb-second-brain/
├─ SKILL.md                    what Claude reads — the five operations
├─ references/
│  ├─ karpathy-model.md        the architecture, and when to add machinery
│  ├─ schema-design.md         how to pick note types (the hard part)
│  ├─ obsidian.md              compliance rules + setup
│  └─ atlas-ui.md              customising and deploying the site
├─ assets/
│  ├─ SCHEMA.template.md       starting point for a new vault
│  └─ site/                    the static viewer
└─ scripts/
   ├─ build_atlas.py           vault → atlas.json
   └─ init_obsidian.py         vault → .obsidian/ config
```

## Credits and licence

Architecture: Andrej Karpathy's LLM-wiki model.

Vendored in `assets/site/vendor/`, both MIT:
[3d-force-graph](https://github.com/vasturiano/3d-force-graph) ·
[marked](https://github.com/markedjs/marked)

Built by [SMB·excel](https://smbexcel.com).

**AI summaries can be wrong.** Every note should link back to its real source,
and any site you publish should keep the disclaimer visible.

## Changelog

- **1.0** — Initial release. Five operations (SETUP / INGEST / QUERY / LINT /
  PUBLISH), Obsidian-native vault output, `build_atlas.py` + `init_obsidian.py`,
  dependency-free graph viewer.
