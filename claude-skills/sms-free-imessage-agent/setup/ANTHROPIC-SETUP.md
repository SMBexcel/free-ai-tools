# Anthropic Setup

This guide gets you an Anthropic API key, a spend limit so a runaway loop can't drain your account, and the right model wired into the Worker. The Worker calls Anthropic to power the conversational agent that replies to inbound texts. Run this once.

**Time:** ~10 minutes. **You'll need:** an email address and (for paid usage) a card.

> The secret you create here is `ANTHROPIC_API_KEY`. The model is set in `wrangler.toml` via the `ANTHROPIC_MODEL_AGENT` public var. Both are covered below.

---

## 1. Create a Console account

1. Go to **[console.anthropic.com](https://console.anthropic.com)** and sign up (or log in).
2. Create or select an **Organization** when prompted. Your API keys, billing, and limits all live under the org.
3. Verify your email if asked.

The Console is the dashboard for keys, billing, usage, and limits. Docs home: **[platform.claude.com/docs](https://platform.claude.com/docs)**.

---

## 2. Add billing and a credit balance

The API is pay-as-you-go and is billed separately from any Claude.ai subscription — a Pro/Max plan does **not** include API credits.

1. In the Console, open **Settings → Billing** (or **Plans & Billing**).
2. Add a payment method.
3. Add an initial credit balance (you can start small, e.g. $5–$20). See **[Pricing](https://platform.claude.com/docs/en/about-claude/pricing)** for current rates.

> Optional but recommended: enable **auto-reload** so the agent doesn't start erroring mid-conversation when the balance hits zero. Pair it with the spend limit in Step 4 so auto-reload can't run away.

---

## 3. Generate an API key (`ANTHROPIC_API_KEY`)

1. In the Console, open **Settings → API Keys**.
2. Click **Create Key**.
3. Name it something traceable, e.g. `imessage-agent-prod`.
4. **Copy the key now** — it's shown only once. It starts with `sk-ant-`.

Store it in the Worker as a secret (run from the project root, one secret at a time):

```bash
wrangler secret put ANTHROPIC_API_KEY
# paste the sk-ant-... value when prompted, then press Enter
```

> Never commit the key or put it in `wrangler.toml`. `wrangler secret put` keeps it encrypted in Cloudflare and out of your repo. If a key leaks, return to **Settings → API Keys**, delete it, and create a new one.

Key-management reference: **[API Keys best practices](https://platform.claude.com/docs/en/api/administration-api)**.

---

## 4. Set a usage / spend limit

A misbehaving prompt loop or an abusive texter can run up cost fast. Cap it before going live.

1. In the Console, open **Settings → Limits** (also surfaced under Billing on some accounts).
2. Set a **monthly spend limit** for the organization (e.g. $25 to start).
3. Optionally set a **lower-balance / usage email alert** so you get warned before you hit the ceiling.

When the limit is reached, the API returns errors instead of continuing to bill. Your Worker should already degrade gracefully (it falls back to a holding reply) — but the limit is your hard backstop.

Reference: **[Rate limits & usage](https://platform.claude.com/docs/en/api/rate-limits)** and the **Limits** tab in the Console.

---

## 5. Pick the agent model and set `ANTHROPIC_MODEL_AGENT`

The kit ships with a default; you set the model as a public var in `wrangler.toml` (it's a model **name**, not a secret).

```toml
# wrangler.toml
[vars]
ANTHROPIC_MODEL_AGENT = "claude-sonnet-4-6"
```

### Default

- **`claude-sonnet-4-6`** — the kit's default. A strong, low-latency Sonnet-tier model that's well-suited to a back-and-forth SMS concierge. It is still available on the API at **$3 / $15 per million input / output tokens**.

> Heads-up on currency: as of mid-2026 Anthropic lists `claude-sonnet-4-6` as a **legacy** model (still callable, not deprecated). The current generation is **Sonnet 5**, **Haiku 4.5**, and **Opus 4.8**. The default above works out of the box; if you'd rather run a current-generation model, see the options below and always confirm the live model ID against the docs — model IDs are pinned snapshots and change between generations.

### Cheaper / faster

- **`claude-haiku-4-5`** — Anthropic's fastest tier with near-frontier intelligence, priced around **$1 / $5 per MTok**. Good when most inbound texts are short, simple, and high-volume, and you want to shave per-message cost and latency.

### For the hardest tasks

- **`claude-opus-4-8`** — Anthropic's most capable Opus-tier model for complex reasoning and long-horizon agentic work, priced around **$5 / $25 per MTok**. Overkill for routine chat; reach for it only if your agent does heavy multi-step reasoning or tool use.

> **Always verify the exact, current model IDs and prices** before you commit — they shift each release. Authoritative sources:
> - **[Models overview](https://platform.claude.com/docs/en/about-claude/models/overview)** — current IDs, context windows, capabilities
> - **[Pricing](https://platform.claude.com/docs/en/about-claude/pricing)** — per-token rates, batch and caching discounts
> - **[Model IDs & versioning](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions)** — how snapshots and aliases work

To change the model, edit the `ANTHROPIC_MODEL_AGENT` value above and redeploy (`wrangler deploy`). No code change needed.

---

## 6. A note on cost: prompt caching keeps it low

The agent re-sends a stable preamble on every turn — your system prompt, business persona, tone rules, and any fixed context. **Prompt caching** lets Anthropic reuse that prefix instead of reprocessing it each message:

- **Cache reads cost ~10% (0.1x) of the base input price** — a ~90% discount on the repeated portion.
- Cache **writes** cost a small premium (~1.25x for the default 5-minute TTL; ~2x for the 1-hour TTL).
- The default cache lifetime is **5 minutes** (refreshed on each hit), with a **1-hour** option available.

For a high-frequency SMS agent where the same system prompt rides along on every reply, this is the single biggest lever on your bill. The kit's agent code marks the stable prefix with `cache_control` so caching kicks in automatically — you don't need to configure anything, just know it's working.

Full details: **[Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)**.

---

## Done when…

- [ ] You can log into **[console.anthropic.com](https://console.anthropic.com)** and see your Organization.
- [ ] A payment method and a starting credit balance are set under **Billing**.
- [ ] An API key (`sk-ant-…`) was created and stored via `wrangler secret put ANTHROPIC_API_KEY` — and is **not** in your repo.
- [ ] A **monthly spend limit** is set under **Limits** (a misbehaving loop can't drain the account).
- [ ] `ANTHROPIC_MODEL_AGENT` is set in `wrangler.toml` (`claude-sonnet-4-6` by default; swap to `claude-haiku-4-5` for cheaper/faster or `claude-opus-4-8` for the hardest tasks — verified against the [Models overview](https://platform.claude.com/docs/en/about-claude/models/overview)).
- [ ] You've redeployed (`wrangler deploy`) if you changed the model, and you understand prompt caching is on by default to keep costs down.
