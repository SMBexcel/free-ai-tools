# Lemonade

**Persistent memory for Claude chats — plug and play.**

> Distill your chat into shelf-stable Notion rows. Rehydrate in the next session. Powder and water, chat after chat.

`v1.2` · MIT · by [David Schreiber](https://www.smbexcel.com)

---

## The problem

The longer any single Claude chat runs, the worse Claude gets at remembering what you told it. This is real — it's called **context rot**, and every frontier model has it. The fix is counterintuitive:

**Short, focused chats with clean context outperform long ones with rich history. Every new chat is a performance reset.**

But you can't start fresh if you have to spend ten minutes re-explaining yourself every time.

## What lemonade does

Two commands run the whole thing:

- **`distill`** at the end of a chat → your work is concentrated into structured Notion rows (STATE, DECISIONS, ROADMAP, ARTIFACT)
- **`rehydrate <project>`** at the start of the next one → those rows reconstitute into instant fresh context

The memory lives in a **Notion database you own**, not in Claude. It survives model upgrades, account changes, and migrations to other tools.

---

## What you get

- **Per-project memory.** Each project gets its own STATE (what's happening now), DECISIONS (every choice and why), ROADMAP (the long arc), and ARTIFACT (versioned drafts).
- **A global learnings bucket.** Cross-chat insights and reference files that aren't tied to any one project.
- **An auto-generated to-do list.** Your "next moves" surface every time you rehydrate.
- **Versioned artifacts.** Every draft Claude generates gets saved as `latest`; the previous `latest` becomes `prev`. One-step rollback.
- **Audit trail.** Every meaningful decision logged with the why, the alternatives, and the reversibility.

---

## Install

### Quickest path — direct zip download

1. **Download:** [lemonade-v1.2.zip](https://github.com/SMBexcel/free-ai-tools/raw/main/claude-skills/lemonade/lemonade-v1.2.zip) (committed in this folder — single click, no Release page needed).
2. **Unzip** — you'll get a `lemonade/` folder containing `SKILL.md` and `references/`.
3. **Drop it into your Claude skills directory:**
   - **Claude Code:** `~/.claude/skills/lemonade/`
   - **claude.ai (Cowork):** install via the Skills UI
4. **Enable the Notion connector** in Claude (Settings → Connectors → Notion). Grant access to a workspace where you want the database to live.
5. **Smoke test** — in any new chat say: *"save learning: setup test"*. On first run the skill will ask once where to create the `Claude Memory` database, create it, then write a test entry. Confirm it appears in your Notion.

### Alternative — clone the whole repo

```bash
git clone https://github.com/SMBexcel/free-ai-tools.git
cp -R free-ai-tools/claude-skills/lemonade ~/.claude/skills/
```

Then enable the Notion connector and run the smoke test above.

### Alternative — copy just the files

If you'd rather not download a zip or clone, you can view each file directly in this folder ([`SKILL.md`](./SKILL.md), [`references/`](./references)) and save them into `~/.claude/skills/lemonade/` manually. The skill is markdown all the way down — no build step, no dependencies.

---

## How to use it

### Daily commands

| Say this... | What happens |
|---|---|
| `distill` (or *"wrap up"*, *"save this chat"*, *"end of session"*) | Saves the chat's state to Notion |
| `rehydrate Acme HVAC` (or *"catch me up on Acme HVAC"*) | Loads everything you know about that project into fresh context |
| `save learning: <insight>` | Logs a cross-chat learning to global memory |
| `log decision` | Records a single decision without a full distill |
| `save artifact <name>` | Versions a single artifact mid-chat |
| `list projects` | Shows everything you're tracking |
| `status Acme HVAC` | Quick "where am I?" without full rehydrate |
| `archive project Acme HVAC` | Closes out a finished project (with confirmation) |

### Typical day

```
Morning chat:
  > rehydrate Acme HVAC
  → "Where you are: ... Open questions: ... Next moves: ..."
  
  [work for an hour]
  
  > distill
  → "Saved STATE, appended 2 decisions, updated 1 artifact. Done."

Afternoon chat (fresh, clean context):
  > rehydrate Beacon Capital
  → "Where you are: ..."
```

Every chat starts at peak performance (clean context), and you never lose your place.

---

## Configuration (all optional)

The skill works out of the box. If you want overrides, edit the config block at the top of `SKILL.md`:

```yaml
DEFAULT_TIMEZONE:      <YOUR_IANA_TIMEZONE>   # e.g. America/Chicago. Defaults to UTC.
DATABASE_NAME:         Claude Memory           # The Notion DB the skill reads/writes.
NOTION_DATA_SOURCE_ID:                          # Override: pin to a specific data source UUID.
SKILL_VERSION:         1.2
```

---

## What's in the Notion database

Lemonade auto-creates this schema on first run — you never set it up manually.

| Column | Type | Purpose |
|---|---|---|
| Row | Title | Human-readable label, e.g. `Acme HVAC · STATE` |
| Project | Text | Project name or `__global__` |
| Type | Select | `STATE` / `DECISIONS` / `ROADMAP` / `ARTIFACT` |
| Slug | Text | ARTIFACT only — title-family key |
| Version | Select | ARTIFACT only — `latest` / `prev` |
| Updated | Last edited time | Auto |
| Skill-Version | Text | Version that wrote the row |

The markdown content lives in the **page body** of each row, not a property — Notion renders it as native blocks you can edit, read, and search.

---

## Failure modes

- **Notion connector unavailable** → skill aborts with a clear error pointing at Settings → Connectors.
- **First run, no database** → skill enters first-run mode and creates one.
- **You manually created a `Claude Memory` DB with wrong columns** → skill aborts with the missing column name; rename your DB so the skill can create a fresh one, or add the column.
- **Multiple matching databases** → skill asks once which one to use.
- **Bad distill overwrote good STATE** → recover via Notion's native page history (right-click → Page history → Restore).

Full details in [`SKILL.md`](./SKILL.md#failure-modes--recovery).

---

## Credit

Lemonade is a Notion port of the GSD (Get Shit Done) filesystem-state pattern. The STATE / DECISIONS / ROADMAP structure and the sweep/rehydrate workflow are theirs — Lemonade just moves the storage from disk to a database so it works in claude.ai chats (which don't have a writable filesystem).

Go give them a star: [github.com/gsd-build/get-shit-done](https://github.com/gsd-build/get-shit-done).

---

## Newsletter

The build notes, the prompt patterns I actually use, and a setup walkthrough ship with the newsletter — plus the next skill before it lands here:

**→ [www.smbexcel.com](https://www.smbexcel.com)**

---

## Changelog

- **1.2** — Plug-and-play. First run auto-creates the Notion database via `notion-create-database`. Setup collapsed from 4 manual steps to 1. No more UUID hunting.
- **1.1** — Removed misleading `Content` column from setup (skill writes to page body). Better data-source-ID instructions. `__archived__/*` namespace protection. Smoke test now produces visible output.
- **1.0** — Initial release.

---

_MIT licensed. © 2026 David Schreiber._
