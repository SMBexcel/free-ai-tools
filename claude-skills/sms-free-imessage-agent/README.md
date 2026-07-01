# sms-free-imessage-agent

A one-shot [Claude Code](https://claude.com/claude-code) **skill** that scaffolds
and deploys a complete, production-ready **iMessage/SMS conversational agent** —
the kind of texting concierge / sales / support bot people message and that takes
real actions on their behalf.

Run it once, answer a few questions, and you get a deployed Cloudflare Worker that:
receives texts through [Blooio](https://blooio.com), runs a [Claude](https://www.anthropic.com)
agent loop with your tools, remembers conversations in [Supabase](https://supabase.com),
and replies — with typing indicators, read receipts, reactions, and link previews.

No demo cruft, no business-specific assumptions — a clean, brand-neutral starting point for **your** product.

---

## What you get

```
 you text the number ──▶  Cloudflare Worker ──▶  Blooio (iMessage/SMS)
                          ├─ HMAC-verified inbound webhook (returns 200 fast)
                          ├─ per-phone Durable Object (debounce + rate limit)
                          ├─ Claude agent loop + your tools
                          └─ Supabase (users, memory, idempotency)
```

- A **compiling, deployable TypeScript project** (`template/`) — `tsc` clean, tests
  passing, `wrangler deploy` ready out of the box.
- The full inbound→agent→reply pipeline: HMAC webhook verification, burst
  coalescing in a Durable Object, a hand-rolled Anthropic Messages loop with prompt
  caching, post-agent guardrails, and a typed Blooio client.
- Example tools (`update_user`, `save_note`, `escalate_to_human`) and a
  sales-concierge system prompt skeleton you tailor to your product.
- An **opt-in referral & affiliate subsystem** (peer credit + influencer cash, one
  attribution path, anti-farming reward model).
- **Setup guides** for Blooio, Cloudflare, Supabase, Anthropic, and MCP connection.
- **Deep-dive reference docs** on the architecture, the agent loop, iMessage UX, and
  prompt engineering.

## How to use it

1. Drop this folder into your Claude Code skills directory, e.g.
   `~/.claude/skills/sms-free-imessage-agent/` (or your project's
   `.claude/skills/`).
2. In Claude Code, run the skill:
   ```
   /sms-free-imessage-agent
   ```
3. Follow the guided, one-time setup. It walks you through the four accounts,
   copies the template, applies the database schema, sets secrets, deploys, wires
   the Blooio webhook, and smoke-tests a real text.

You can also just hand the project in `template/` to any developer — it's a normal
`npm install && npm run deploy` Cloudflare Worker.

## What you'll need

- A [Blooio](https://blooio.com) account + an iMessage-capable number
- A [Cloudflare](https://dash.cloudflare.com) account (Workers; Durable Objects enabled)
- A [Supabase](https://supabase.com) project
- An [Anthropic API](https://console.anthropic.com) key
- Node 20+ and `wrangler`

See [`setup/`](setup/) for step-by-step guides for each.

## What's in here

| Path | What it is |
|---|---|
| [`SKILL.md`](SKILL.md) | The skill itself — the guided setup runbook Claude Code follows. |
| [`OVERVIEW.md`](OVERVIEW.md) | Plain-English overview for business owners (non-technical). |
| [`DEVELOPER.md`](DEVELOPER.md) | Developer guide: layout, dev loop, extension points, config, troubleshooting. |
| [`template/`](template/) | The complete Worker project that gets scaffolded. |
| [`setup/`](setup/) | Per-platform account-setup guides (Blooio, Cloudflare, Supabase, Anthropic, MCP). |
| [`reference/`](reference/) | Deep-dive architecture docs (also copied into the new project's `docs/`). |
| [`scripts/`](scripts/) | Helpers: `set-secrets.sh`, `verify-setup.mjs`. |

## The stack

| Layer | Choice |
|---|---|
| Runtime | Cloudflare Workers (module worker) |
| Router | Hono |
| Conversation state | Durable Objects (SQLite) |
| Messaging | Blooio v2 API |
| Agent | Anthropic Claude (Messages API) |
| Data | Supabase (PostgREST + service-role key) |

---

Brand-neutral and unaffiliated with any specific business — use it for whatever you're building.
