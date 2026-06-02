# Free AI Tools

Free, open-source AI tooling for searchers, investors, and operators — built and maintained by [SMBexcel](https://www.smbexcel.com).

Two kinds of tools live here:

| | | |
|---|---|---|
| 🧠 | **[Claude Skills](./claude-skills)** | Self-contained skills you drop into Claude. No build step, no install script — markdown all the way down. |
| ⚙️ | **[AI Workflows](./ai-workflows)** | Importable [n8n](https://n8n.partnerlinks.io/qsoyb0o2mh2x) automations that wire Claude into your daily search-and-buy operations. |

---

## 🧠 Claude Skills

→ **[Browse all skills](./claude-skills)**

| Skill | Version | What it does |
|---|---|---|
| [lemonade](./claude-skills/lemonade) | `1.2` | Plug-and-play persistent memory for Claude chats. Distill / rehydrate via a Notion database you own. Counters context rot. |
| [smb-find-ibba](./claude-skills/smb-find-ibba) | `1.1` | Get every IBBA business broker (~2,800) into a single CSV — name, company, email, phone, website, location, credentials — from the directory's own public endpoints. No login, no cookie, no paid tool. Resumable, merges on re-run. **Claude Code only.** |

## ⚙️ AI Workflows

→ **[Browse all workflows](./ai-workflows)**

| Workflow | Version | What it does |
|---|---|---|
| [smb-bizquest-daily](./ai-workflows/smb-bizquest-daily) | `1.0` | Daily BizQuest scrape → Claude scores each listing against your buy box → drafts broker outreach for the strong fits → posts the shortlist to Slack, logs everything to a Google Sheet. |

More shipping soon — see the [SMBexcel newsletter](https://www.smbexcel.com) for what's next.

---

## How to use these

Each tool is a self-contained folder with its own `README.md` covering setup. The short version:

- **Skills** → download the folder's `<skill>-vX.Y.zip` (or clone the repo), drop it into your Claude skills directory (`~/.claude/skills/` for Claude Code), then follow the skill's README.
- **Workflows** → download the folder's `<workflow>.json`, import it into n8n (**Workflows → ⋯ → Import from File**), wire your credentials, and go.

Full per-category instructions live in [`claude-skills/`](./claude-skills) and [`ai-workflows/`](./ai-workflows).

---

## Versioning

Everything follows `MAJOR.MINOR` (e.g. `1.2`). Breaking changes bump MAJOR; additive changes bump MINOR. Each tool's own `README` / `SKILL.md` carries its version and changelog, and ships a git tag (`<name>-vX.Y`).

---

## Contributing

Issues and pull requests welcome — file under the relevant tool folder. Bug reports especially helpful; if you hit something weird in your own setup, open an issue.

---

## License

MIT, unless a specific tool folder overrides it. See [LICENSE](./LICENSE).

---

## More

- Newsletter: [www.smbexcel.com](https://www.smbexcel.com)
- Organization: [github.com/SMBexcel](https://github.com/SMBexcel)
- Author: David Schreiber
