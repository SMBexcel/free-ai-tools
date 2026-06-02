# SMBexcel — Skills & Workflows

Open-source Claude **skills** and n8n **workflows** built and maintained by [SMBexcel](https://www.smbexcel.com).

Skills are self-contained folders you drop into your Claude skills directory — no build step, no install script, markdown all the way down. Workflows are importable [n8n](https://n8n.partnerlinks.io/qsoyb0o2mh2x) automations that wire Claude into your daily search-and-buy operations.

---

## Skills

| Skill | Version | What it does |
|---|---|---|
| [lemonade](./lemonade) | `1.2` | Plug-and-play persistent memory for Claude chats. Distill / rehydrate via a Notion database you own. Counters context rot. |
| [smb-find-ibba](./smb-find-ibba) | `1.1` | Get every IBBA business broker (~2,800) into a single CSV — name, company, email, phone, website, location, credentials — from the directory's own public endpoints. No login, no cookie, no paid tool. Resumable, merges on re-run. Legal-posture briefing included. **Claude Code only.** |

## Workflows

n8n automations live under [`workflows/`](./workflows), each with its own README and importable JSON.

| Workflow | Version | What it does |
|---|---|---|
| [smb-bizquest-daily](./workflows/smb-bizquest-daily) | `1.0` | Daily BizQuest scrape → Claude scores each listing against your buy box → drafts broker outreach for the strong fits → posts the shortlist to Slack, logs everything to a Google Sheet. |

More shipping soon — see the [SMBexcel newsletter](https://www.smbexcel.com) for what's next.

---

## Installing a skill

Each skill folder has its own `README.md` with skill-specific setup, but the general pattern:

### Option 1 — Download the per-skill zip (recommended for non-developers)

Each skill folder has its own committed `<skill>-vX.Y.zip` you can grab in one click — no Releases page required.

1. Open the skill folder above (e.g. [`smb-find-ibba`](./smb-find-ibba)).
2. Click the `<skill>-vX.Y.zip` file → **Download raw file**.
3. Unzip. Drop the folder into your Claude skills directory:
   - **Claude Code** (CLI): `~/.claude/skills/<skill-name>/`
   - **claude.ai** (Cowork mode): install via the Skills UI
4. Open the skill's `README.md` for any one-time setup (connectors, config, etc.).

### Option 2 — Clone the whole repo (developers / CLI)

```bash
git clone https://github.com/SMBexcel/skills.git
cp -R skills/smb-find-ibba ~/.claude/skills/
```

Then follow the per-skill README.

---

## Requirements

Requirements vary by skill — some need MCP connectors (e.g. lemonade needs Notion), some run only in Claude Code with a shell (e.g. smb-find-ibba needs `bash`, `curl`, `python3`). Each skill's README lists exactly what it needs.

---

## Versioning

- Skills follow semver-ish: `MAJOR.MINOR` (e.g. `1.2`).
- Each version ships a downloadable zip (`<skill>-vX.Y.zip`) committed inside its skill folder.
- Breaking changes bump MAJOR; behavior-additive changes bump MINOR. The skill's own `SKILL.md` always carries its `Version:` field and a changelog at the bottom.

---

## Contributing

Issues and pull requests welcome — file under the relevant skill folder. Bug reports especially helpful; if you hit something weird in your own setup, open an issue.

---

## License

MIT, unless a specific skill folder overrides it. See [LICENSE](./LICENSE).

---

## More

- Newsletter: [www.smbexcel.com](https://www.smbexcel.com)
- Organization: [github.com/SMBexcel](https://github.com/SMBexcel)
- Author: David Schreiber
