---
name: lemonade
description: Plug-and-play persistent memory for Claude chats backed by a Notion database you own. First run auto-creates the database — no manual table setup. `distill` at the end of a chat concentrates your work into shelf-stable Notion rows; `rehydrate` at the start of the next one reconstitutes them into instant fresh context. Powder and water — chat after chat. Per-project STATE / DECISIONS / ROADMAP / ARTIFACT rows plus a `__global__` bucket for cross-chat learnings and reference files. Use this skill AGGRESSIVELY when the user says "distill", "rehydrate", "make lemonade", "save this chat", "wrap up", "catch me up", "log this decision", "save learning", "save reference", "remember this", "continue where we left off", or opens a chat naming an ongoing project without supplying context (that's a rehydrate signal). YOLO writes — never ask before writing; summarize after. If the Notion connector isn't enabled, surface a setup error and stop instead of writing partial state.
---

# Lemonade

Persistent memory for Claude chats. Every session ends with a `distill` — your chat concentrates into shelf-stable Notion rows. Every new session begins with a `rehydrate` — those rows reconstitute into instant fresh context. Powder and water, chat after chat. Modeled after GSD's filesystem state pattern (`STATE.md`, `DECISIONS.md`, `ROADMAP.md`), but stored as rows in a single Notion database you own. Each row is a markdown "file" scoped to either a real project OR the reserved `__global__` bucket.

The data lives in your Notion — not in Claude — so it survives model upgrades, account changes, and migrations to other tools. The lemonade is yours to keep.

---

## Setup

Plug-and-play. One required step, one optional, then use it.

### 1. Connect Notion in Claude (required)

In Claude.ai, enable the Notion connector and grant access to a workspace where the skill is allowed to create a database. In Cowork / API contexts, ensure the Notion MCP tools are available (`notion-search`, `notion-fetch`, `notion-create-database`, `notion-create-pages`, `notion-update-page`, `notion-update-data-source`).

### 2. (Optional) Set your timezone

Edit the config block below if you want stamps in your local time. Defaults to UTC if unset. Everything else is optional and has sensible defaults.

```yaml
# CONFIGURATION — all fields optional, sensible defaults applied
DEFAULT_TIMEZONE:      <YOUR_IANA_TIMEZONE>    # e.g. America/Chicago. Defaults to UTC if blank.
DATABASE_NAME:         Claude Memory           # The Notion database name the skill reads/writes. Default: Claude Memory.
NOTION_DATA_SOURCE_ID:                          # Override: pin to a specific data source UUID. If blank, the skill discovers by DATABASE_NAME.
SKILL_VERSION:         1.2
```

### 3. First run (just use it)

The first time you say `distill`, `save learning`, or any other write command, the skill enters **first-run mode** and bootstraps itself:

1. Searches Notion for a database matching `DATABASE_NAME` (default `Claude Memory`).
2. **If found** → caches the data source ID for this turn and proceeds with your command.
3. **If not found** → asks you once: *"I'll create the `Claude Memory` database for you. Drop a Notion page link to put it under, or say 'workspace root' to put it at the top of your default workspace."*
4. Calls `notion-create-database` with the canonical schema (below). The page body itself holds each row's markdown — no `Content` property is created because Notion text properties cap at ~2,000 chars and would silently truncate.
5. Proceeds with the original command using the new database.

You never manually create columns, never hunt for a UUID, never paste anything into the config block (unless you want overrides).

### Canonical schema (created by the skill)

For reference — what `notion-create-database` provisions on first run. You do not need to do this manually.

| Column        | Type             | Notes                                                              |
|---------------|------------------|--------------------------------------------------------------------|
| Row           | Title            | Default title column. Human label, e.g. `Acme HVAC · STATE`.     |
| Project       | Text             | Project name or `__global__`. Text (not Select) for fuzzy match.   |
| Type          | Select           | Options: `STATE`, `DECISIONS`, `ROADMAP`, `ARTIFACT`.              |
| Slug          | Text             | ARTIFACT only — title-family key. Empty otherwise.                 |
| Version       | Select           | ARTIFACT only — options: `latest`, `prev`. Empty otherwise.        |
| Updated       | Last edited time | Auto-populated by Notion.                                          |
| Skill-Version | Text             | Skill version that wrote the row. Used for future migrations.      |

**Markdown content lives in the Notion page body** (block content) — not a property. When this SKILL says "rewrite the row's Content" it means rewrite the page body via `notion-update-page`. When it says "read existing Content" it means fetch the page body via `notion-fetch`.

### 4. Smoke test

After install, in any new chat say: *"save learning: setup test"*. Expected behavior:

- If first run: the skill asks where to create the database, creates it, then writes one entry to `Global · DECISIONS`.
- If already initialized: the skill writes one entry directly.

Either way you'll see a confirmation. Open Notion → the `Claude Memory` database should exist with one `Global · DECISIONS` row whose page body contains your test entry.

---

## Project mode vs. global mode

The skill operates in two modes, distinguished only by the `Project` column value:

- **Project mode** — `Project` column = a real project name (e.g., `Acme HVAC`, `Beacon Capital`). Supports all four Types: STATE, DECISIONS, ROADMAP, ARTIFACT.
- **Global mode** — `Project` column = `__global__`. Supports only DECISIONS (general learnings) and ARTIFACT (reference files). No STATE — there's no single "current focus" for everything. No ROADMAP — there's no single arc. Just a running learnings log and an artifact stash.

**Defaulting**: When the user invokes the skill in a chat with no clear project context, default to `__global__` without asking. A chat "has project context" if the user named a project, OR earlier in the same chat the skill already resolved one, OR the chat is clearly about a known project (its name appears in the Project column of existing rows). Otherwise, global.

---

## Schema

One row per file. The skill auto-creates the schema on first run (see Setup §3 for the canonical column list). Row title convention:

- Project: `<Project> · <Type>` (e.g. `Acme HVAC · STATE`)
- Artifact: `<Project> · ARTIFACT · <Slug> · <Version>`
- Global: `Global · DECISIONS` or `Global · ARTIFACT · <Slug> · <Version>` (friendly "Global" in the title, `__global__` in the Project column for queryability).

**Never query by row title.** Always query by `Project + Type [+ Slug + Version]`. Users may rename row titles in Notion; the column values are the contract.

---

## What each Type holds

- **STATE** — the rehydration snapshot. One per project. Overwritten on every distill. Schema in `references/state-template.md`. *Project mode only — never written for `__global__`.*
- **DECISIONS** — running KDD log (or in global mode, a learnings log). One per project (or one for `__global__`). Append-only, reverse-chronological. Schema in `references/decisions-template.md`. **Subject to rotation — see "Rotation & limits" below.**
- **ROADMAP** — the long arc. One per project. Updated only when scope shifts. Schema in `references/roadmap-template.md`. *Project mode only — never written for `__global__`.*
- **ARTIFACT** — versioned file storage. Up to 2 rows per `(project × slug)`: `latest` + `prev`. Title-family rules in `references/title-family-rules.md`.

---

## Commands

### `distill` (or "save this chat", "wrap up", "end of session")

End-of-chat writeback. YOLO mode — write everything, summarize after.

1. **Pre-flight check.** Verify the Notion connector responds to a lightweight `notion-search`. If it doesn't, abort with: *"Notion connector not responding. Reconnect in Settings → Connectors, then re-run."* Then **resolve the data source**:
   - If `NOTION_DATA_SOURCE_ID` is set in the config block, use it.
   - Else `notion-search` for `DATABASE_NAME` (default `Claude Memory`). If exactly one match, cache its data source ID for the current turn. If multiple matches, ask the user which one to use (then cache the choice). **If zero matches, enter first-run mode** (see Setup §3): ask the user where to create the database, call `notion-create-database` with the canonical schema, then proceed.
   - Cache the resolved data source ID for the remainder of the turn — don't re-search on every command.
2. **Identify the project.** If the user named one ("for Acme HVAC"), use it. Otherwise check: does the chat clearly reference a known project (name appears in existing rows' Project column, case-insensitive substring match)? If yes, use that project. **If no project context at all, use `__global__`.** Only ask if there's genuine ambiguity (e.g., two known projects mentioned roughly equally).
3. **Read existing rows for this Project value.** Query the database filtered by `Project = <resolved name>`. You need to know which rows already exist before you decide create vs. update.
4. **Idempotency gate (best-effort).** If you ran `distill` earlier in this same turn AND no new artifacts/decisions have been generated in the chat since that call, treat the second invocation as a no-op and report "Already distilled in this turn — nothing new to write." This is a best-effort check; Claude can't reliably reason about "everything since a Notion timestamp" — only about what happened in the current conversation.
5. **Rewrite STATE** using the template. Single row, overwritten. Stamp `Skill-Version` column. *Skip entirely in global mode.*
6. **Append to DECISIONS.** For each KDD-worthy moment (architectural choice, schema lock-in, trade-off; in global mode: any cross-chat learning): read existing Content, prepend new entries at the top using the DECISIONS template, rewrite. Create the row if it doesn't exist. **Apply rotation if Content exceeds the limit (see Rotation & limits).**
7. **Update ROADMAP** only if scope/milestones/"what we're building" shifted in this chat. Otherwise leave alone. *Skip entirely in global mode.*
8. **Write ARTIFACTS.** For each artifact generated in this chat:
   - Compute title-family (see `references/title-family-rules.md`).
   - Query existing ARTIFACT rows for `(Project, Slug)`. If a `latest` exists, demote it to `prev` (overwriting any existing `prev` for that family). Write the new artifact as `latest`.
   - If multiple versions of the same family appeared in one chat, only the FINAL version becomes the new `latest`.
   - In global mode, raise the bar: only save if the user explicitly says to OR the artifact is clearly a reusable template/snippet/example.
9. **Summarize to the user**: "Distilled STATE, appended N decisions, updated M artifact families. Done." (Global mode: "Saved N learnings, M reference artifacts to global. Done.")

### `rehydrate <project>` (or "catch me up on X", "continue X", "load X context")

Start-of-chat rehydration. Read the project's rows and present.

**For project rehydrate:**

1. **Pre-flight check** (same as distill).
2. **Find the project's rows.** Query `Project = <project>` (case-insensitive substring match if exact-match returns nothing — if multiple candidates match, ask).
3. **Read STATE** (full Content).
4. **Read ROADMAP** (full Content, but summarize the Active Phase — don't dump the arc unless asked).
5. **Read DECISIONS** (top 5 entries — the row is reverse-chronological).
6. **List ARTIFACTS** with `Version = latest` (titles, slugs, types — don't dump content unless asked).
7. **Present in this order:**
   - **Where we are**: STATE's `Current Focus` + `Last Session Summary`
   - **Open questions**: STATE's `Open Questions`
   - **Next moves**: STATE's `Next Moves`
   - **Roadmap position**: 1–2 lines on where the project is in its arc
   - **Recent decisions**: last 5 from DECISIONS, one-line each
   - **Latest artifacts**: titles only
   - **Suggested next step**: from STATE's `Suggested Next Step`, or inferred
8. **End with**: "Ready when you are. What are we working on?"

**For `rehydrate global` (or "what have I learned", "show me global learnings"):**

1. Query `Project = __global__`.
2. Read the DECISIONS row's top 10 entries.
3. List all `latest` ARTIFACT titles + slugs.
4. Present as: "Recent global learnings (last 10):" + "Reference artifacts saved:" with titles.
5. No STATE, no ROADMAP, no "next step" inference.

### `status <project>` (or "where am I on X")

Lightweight. Read STATE only. Show `Current Focus` and `Last Updated`. Done.

### `list projects`

Query distinct values in the `Project` column, **excluding any value that starts with `__`** (so `__global__`, `__archived__/*`, and any other reserved namespaces are hidden). Return as a list with each project's STATE `Last distilled` date if available. Use this when the user asks "what am I tracking" or "what projects do I have."

To see archived projects, the user must explicitly ask: *"list archived projects"* — then return values matching `__archived__/*`.

### `archive project <name>`

End-of-project cleanup. **This command breaks YOLO** — confirm once before acting.

1. Query all rows for `Project = <name>`.
2. Combine their Content into a single markdown bundle.
3. Write one new row with `Project = __archived__/<name>`, `Type = ARTIFACT`, `Slug = archive-snapshot`, `Version = latest`, Content = the bundle, with a header `# {name} — Archive ({YYYY-MM-DD})`.
4. Set every original row's `Project` column to `__archived__/<name>` (rows become invisible to `list projects` and project resolution; they remain readable in Notion and via explicit "rehydrate the archive of X" requests).
5. Report: "Archived N rows for `<name>`. Snapshot saved. They will no longer appear in `list projects` — say *'list archived projects'* to see them."

**After archive**, the protection rules apply: no `distill`/`rehydrate` against the archived name unless the user explicitly references the archive. To revive an archived project, the user must say so explicitly (e.g., *"un-archive Acme HVAC"*) — the skill should then rename `__archived__/<name>` back to `<name>` on all rows.

### `log decision` (or "this is a KDD")

Mid-chat append to DECISIONS without full distill. Uses currently-resolved project (or `__global__`). Asks for: decision, rationale, alternatives, reversibility. Read existing Content → prepend new entry → rewrite.

### `save learning` (or "remember this", "save this insight")

Mid-chat append to the `__global__` DECISIONS row regardless of current chat's project context. Use when the insight is cross-cutting. Reversibility defaults to "Two-way door."

### `save artifact <name>` (or "save this version")

Mid-chat write of one artifact without full distill. Uses currently-resolved project (or `__global__`). Compute title-family → demote `latest` to `prev` → write new `latest`.

### `save reference <name>` (or "save this as a reference")

Mid-chat write of one artifact to `__global__` regardless of current chat's project context. Use for cross-project reusable assets.

---

## Critical operating rules

- **YOLO writes** — Never ask for confirmation, EXCEPT for `archive project`, explicit user-initiated overwrites, and the one-time first-run "where to put the database?" question. Write first, summarize after.
- **Pre-flight first** — Every command must verify the Notion connector and resolve the data source before any write. Better to fail loudly than to write to the wrong place.
- **First-run auto-create, otherwise never modify schema** — If no matching database exists, the skill creates one (asking once for parent location). If a database with the canonical schema already exists, use it as-is. Never auto-modify an existing database's schema, never auto-create a second database with the same name. If the user has a database that looks like ours but with columns missing or renamed, abort with a clear error (see Failure modes).
- **Default to global** — If no project context exists, default to `__global__` without asking.
- **Never write STATE/ROADMAP to `__global__`** — Refuse and explain why.
- **Never write to `__archived__/*` without explicit opt-in** — Archived projects are dormant. Refuse `distill`, `rehydrate`, or any other write/read against `__archived__/<name>` unless the user explicitly references the archived namespace (e.g., *"rehydrate the archive of Acme HVAC"*). Project resolution must also exclude `__*` namespaces from substring matching, so typing "acme hvac" never accidentally targets `__archived__/acme hvac`.
- **Reserved namespaces** — Any Project value starting with `__` (double underscore) is reserved (`__global__`, `__archived__/*`, future reservations). The skill must not create new `__*` namespaces beyond these two.
- **Query by columns, not titles** — Users rename row titles in Notion; rely on `Project + Type [+ Slug + Version]`.
- **DECISIONS is append-only** — Always read existing Content first, prepend, rewrite. Never overwrite blindly.
- **STATE is overwrite-only** — Generate the whole snapshot fresh each distill.
- **Idempotency (best-effort)** — If `distill` runs twice in the same turn with no new artifacts/decisions since the prior call, treat the second as a no-op. Don't try to reason about "since when" across turns or Notion timestamps — Claude can only see the current conversation.
- **Markdown only in Content** — No JSON. Markdown renders in Notion if the user peeks.
- **Decision-worthiness (project mode)** — Log it if reversing would cost real time (architectural, schema, library, naming, business logic). Skip casual choices.
- **Learning-worthiness (global mode)** — Log it if you'd want to know this fact/pattern in a different chat 3 months from now.
- **Artifact-worthiness (global mode)** — Higher bar than project mode. Explicit save request OR clearly reusable template/snippet.
- **Project resolution** — Exact match on `Project` column first, excluding any value starting with `__`. If zero, case-insensitive substring (still excluding `__*`). If multiple, ask once. If still zero, use `__global__`. To target an archived project, the user must say so explicitly (e.g., *"the archived Acme HVAC"*).
- **Skill-Version stamp** — On every write, set the `Skill-Version` column to the configured `SKILL_VERSION` so future migrations can detect old rows.

---

## Rotation & limits

Notion's text properties have practical limits (~2,000 blocks per page; long-text properties around 100K characters in practice). DECISIONS rows are append-only and will eventually hit them.

**Rotation rule for DECISIONS:**

- If the existing Content exceeds **40,000 characters** when you try to prepend, do this:
  1. Split the existing Content roughly in half at a `---` separator boundary (newer half kept, older half archived).
  2. Create a new row: same `Project`, `Type = ARTIFACT`, `Slug = decisions-archive-<YYYY-MM>`, `Version = latest`, Content = the older half with a header `# {Project} — Decisions Archive (through {oldest date} to {newest archived date})`.
  3. Rewrite the original DECISIONS row with just the newer half + your new prepended entries.
  4. Note the rotation in your distill summary so the user knows.

**ARTIFACTS:**

- If an artifact's Content exceeds 90,000 characters, split it into `<slug>-part-1`, `<slug>-part-2`, etc. — each as its own family. Note this in the distill summary.

---

## Failure modes & recovery

- **Notion connector unavailable** — Pre-flight fails. Abort with: "Notion connector not responding. Reconnect in Settings → Connectors, then re-run." Do not partial-write.
- **Database not found on first run** — Expected. Enter first-run mode and create one (see Setup §3). Not a failure.
- **Database schema mismatch (pre-existing DB has wrong columns)** — Happens only if the user manually created a database with the canonical name but with missing/renamed columns. Abort with: *"Found a `Claude Memory` database but its schema doesn't match (missing column: `<name>`). Either rename your existing database (so the skill can create a fresh one), set `DATABASE_NAME` in config to point at a different name, or add the missing column manually."* Do not auto-modify — the user may have intentionally customized.
- **Multiple matching databases** — `notion-search` returns more than one match for `DATABASE_NAME`. Ask the user which one to use, then either pin via `NOTION_DATA_SOURCE_ID` for next time or accept the choice for this turn only.
- **Bad distill overwrote good STATE** — Notion preserves page history per row. Recovery: open the STATE row in Notion → `...` → `Page history` → restore previous version. The skill does not provide an `undo-distill` because Notion's native history is more reliable.
- **Concurrent distills from two chats** — Last write wins. To reduce risk: re-read STATE immediately before writing it; if the `Last distilled` timestamp changed since you started, abort and report "Concurrent distill detected — re-run."
- **Project name collision** — `Acme HVAC` and `Acme HVAC 2` both match a fuzzy search. The skill asks once; never guesses.
- **Migrations** — If `SKILL_VERSION` in config is newer than the `Skill-Version` column on a row being read, behave normally but note in the distill summary so the user knows there are rows from an older schema (for now, no auto-migration).

---

## Tools to use

- `notion-search` — discover the `Claude Memory` database on first run; find rows for a project at any time. Pass `collection://<data-source-id>` and a query string.
- `notion-create-database` — first-run only. Create the canonical schema under a user-specified parent page (or workspace root). Used exactly once per workspace, ever.
- `notion-fetch` — read full Content (page body) of a specific row.
- `notion-create-pages` with `parent.data_source_id = <data-source-id>` — write new rows.
- `notion-update-page` — update existing rows (STATE overwrite, DECISIONS append-rewrite, ARTIFACT version demotion).
- `notion-update-data-source` — only if needed to retitle/restructure (currently unused; reserved for future schema migrations).

(Tool names may be prefixed with an MCP namespace like `mcp__<server-id>__notion-search` depending on environment — use whichever name the connector exposes.)

---

## Reference files

- `references/state-template.md` — STATE row Content format
- `references/decisions-template.md` — DECISIONS row Content format
- `references/roadmap-template.md` — ROADMAP row Content format
- `references/title-family-rules.md` — Artifact name → family collapse rules

---

## About this skill

- **Version:** 1.2
- **Last updated:** 2026-05-17
- **Author:** David Schreiber
- **Newsletter:** [www.smbexcel.com](https://www.smbexcel.com)
- **License:** MIT

**Changelog**

- **1.2** — **Plug-and-play.** First run now auto-creates the Notion database via `notion-create-database` with the canonical schema — no manual table creation, no UUID hunting, no config block to fill (unless you want overrides). Setup collapsed from 4 steps to 1 required step. Pre-flight on every command now resolves the data source by name (`DATABASE_NAME`, default "Claude Memory") instead of requiring `NOTION_DATA_SOURCE_ID` in config. New failure-mode entries for "database not found on first run" (expected, not a failure) and "multiple matching databases" (ask once). Removed duplicate idempotency rule in critical-rules section that contradicted v1.1's in-turn scoping.
- **1.1** — Fixed: `Content` column removed from setup (skill writes to page body, not a property). Fixed: data source ID instructions now lead with `notion-search` rather than URL parsing. Added: `__archived__/*` namespace is now hidden from `list projects` and project resolution; explicit user opt-in required to write/read against it. Added: `un-archive` flow. Weakened: idempotency gate is now scoped to in-turn re-runs (Claude can't reliably reason across Notion timestamps). Changed: `DEFAULT_TIMEZONE` is now a `<YOUR_IANA_TIMEZONE>` placeholder. Smoke test now uses `save learning: setup test` so it always produces visible output.
- **1.0** — Initial release.

```
MIT License

Copyright (c) 2026 David Schreiber

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Credit & inspiration

The structural pattern behind Lemonade — `STATE`, `DECISIONS`, `ROADMAP` as persistent filesystem state, plus the distill/rehydrate workflow — is lifted directly from **GSD (Get Shit Done)**: <https://github.com/gsd-build/get-shit-done>. Lemonade ports that pattern out of the filesystem and into a Notion database so it works for claude.ai chats (which don't have a writable filesystem). All thanks to the GSD authors for the design — go give them a star.
