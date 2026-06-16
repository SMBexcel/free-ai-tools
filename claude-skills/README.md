# Claude Skills

Open-source Claude skills built and maintained by [SMBexcel](https://www.smbexcel.com).

Each skill is a self-contained folder you drop into your Claude skills directory. No build step, no install script — markdown all the way down.

---

## Catalog

| Skill | Version | What it does |
|---|---|---|
| [lemonade](./lemonade) | `1.2` | Plug-and-play persistent memory for Claude chats. Distill / rehydrate via a Notion database you own. Counters context rot. |
| [smb-find-ibba](./smb-find-ibba) | `1.1` | Get every IBBA business broker (~2,800) into a single CSV — name, company, email, phone, website, location, credentials — from the directory's own public endpoints. No login, no cookie, no paid tool. Resumable, merges on re-run. Legal-posture briefing included. **Claude Code only.** |
| [smb-free-website](./smb-free-website) | `1.0` | A real, distinctive small-business website live at your own free URL in ~20 minutes. Claude scaffolds Astro, designs through a self-improving screenshot-driven loop, then walks you through GitHub + Cloudflare. No credit card, no design experience, no `gh` or Homebrew install. **Claude Code only.** Apache 2.0 (skill folder overrides repo MIT). |

---

## Installing a skill

Each skill folder has its own `README.md` with skill-specific setup, but the general pattern:

### Option 1 — Download the per-skill zip (recommended for non-developers)

1. Open the skill folder above (e.g. [`smb-find-ibba`](./smb-find-ibba)).
2. Click the `<skill>-vX.Y.zip` file → **Download raw file**.
3. Unzip. Drop the folder into your Claude skills directory:
   - **Claude Code** (CLI): `~/.claude/skills/<skill-name>/`
   - **claude.ai** (Cowork mode): install via the Skills UI
4. Open the skill's `README.md` for any one-time setup (connectors, config, etc.).

### Option 2 — Clone the whole repo (developers / CLI)

```bash
git clone https://github.com/SMBexcel/free-ai-tools.git
cp -R free-ai-tools/claude-skills/smb-find-ibba ~/.claude/skills/
```

Then follow the per-skill README.

---

## Requirements

Requirements vary by skill — some need MCP connectors (e.g. lemonade needs Notion), some run only in Claude Code with a shell (e.g. smb-find-ibba needs `bash`, `curl`, `python3`). Each skill's README lists exactly what it needs.

---

## License

MIT, unless a specific skill folder overrides it. See the [repository LICENSE](../LICENSE).

---

### More → [www.smbexcel.com](https://www.smbexcel.com)
