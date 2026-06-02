# AI Workflows

Open-source [n8n](https://n8n.partnerlinks.io/qsoyb0o2mh2x) workflows built and maintained by [SMBexcel](https://www.smbexcel.com).

Each workflow is a self-contained folder with an importable `.json` and its own `README.md` covering setup, credentials, and customization. Drop the JSON into n8n, wire your credentials, and go.

---

## Catalog

| Workflow | Version | What it does |
|---|---|---|
| [smb-bizquest-daily](./smb-bizquest-daily) | `1.0` | Scrapes new BizQuest listings every morning, scores each against your buy box with Claude Haiku, drafts a personalized broker outreach for the strong fits with Claude Sonnet, and posts the shortlist to Slack — with every listing logged to a Google Sheet for an audit trail. |

More shipping soon — see the [SMBexcel newsletter](https://www.smbexcel.com) for what's next.

---

## Installing a workflow

1. Open the workflow folder above (e.g. [`smb-bizquest-daily`](./smb-bizquest-daily)).
2. Download its `<workflow>.json` → **Download raw file**.
3. In n8n: **Workflows → ⋯ → Import from File** and select the JSON.
4. Follow the workflow's `README.md` to wire credentials and edit the config nodes.

---

## Requirements

Requirements vary by workflow, but most need an [n8n](https://n8n.partnerlinks.io/qsoyb0o2mh2x) instance (cloud or self-hosted) plus credentials for the services they touch (e.g. Anthropic, Google Sheets, Slack, Apify). Each workflow's README lists exactly what it needs and roughly what it costs to run.

---

## Versioning

- Workflows follow `MAJOR.MINOR` (e.g. `1.0`).
- Breaking changes to node structure or required config bump MAJOR; additive tweaks bump MINOR.

---

## License

MIT, unless a specific workflow folder overrides it. See the [repository LICENSE](../LICENSE).

---

### More → [www.smbexcel.com](https://www.smbexcel.com)
