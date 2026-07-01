# Blooio Setup

This guide gets you from "no account" to "Blooio is delivering inbound iMessages to your
deployed Worker." You'll create an account, provision an iMessage-capable number, grab your
API key, create the inbound webhook (which gives you the HMAC signing secret), and point it
at your Worker.

**Do this once, near the end of setup** — you need your deployed Worker URL
(`WORKER_BASE_URL`) before you can register the inbound webhook in step 6. If you haven't
deployed the Worker yet, finish the Cloudflare deploy first, then come back here.

Official references:
- Dashboard: <https://app.blooio.com>
- Docs home: <https://docs.blooio.com>
- Quickstart: <https://docs.blooio.com/quickstart>
- Authentication: <https://docs.blooio.com/authentication>
- Webhooks: <https://docs.blooio.com/webhooks>
- API reference: <https://docs.blooio.com/reference>
- Pricing: <https://blooio.com/#pricing>

> **Values change.** Plan names, prices, per-day contact caps, and which features sit behind
> which tier are set by Blooio and move over time. Treat the numbers in this guide as a
> starting point and confirm the current details on the official pages linked above before
> you pick a plan.

---

## What the kit expects (the contract)

The Worker in this kit is hardwired to a specific Blooio integration shape. You don't need to
change any of this — just make the dashboard match it:

| Thing | Value |
|---|---|
| API base URL | `https://backend.blooio.com/v2/api/...` |
| Auth header | `Authorization: Bearer <BLOOIO_API_KEY>` |
| Inbound webhook URL | `<WORKER_BASE_URL>/webhooks/blooio` |
| Signature header | `x-blooio-signature` (Stripe-style: `t=...,v1=...`) |
| Signature secret | `BLOOIO_HMAC_SECRET` (the webhook signing secret) |

> **Note on the base host.** The kit calls Blooio at `backend.blooio.com`. Some of Blooio's
> marketing pages reference `api.blooio.com` for the same `/v2/api` surface. Use what the kit
> ships with (`backend.blooio.com`) unless Blooio's current
> [API reference](https://docs.blooio.com/reference) tells you otherwise for your account — if
> so, update the base URL in the Worker source to match and redeploy.
>
> **Note on the signature format.** Blooio signs each webhook with **HMAC-SHA256** over a
> timestamped payload and sends it in the `x-blooio-signature` header. This kit verifies it
> Stripe-style (`t=<timestamp>,v1=<hmac>`). If Blooio changes the wire format, the canonical
> spec is the [webhooks doc](https://docs.blooio.com/webhooks) — match the verifier in the
> Worker to whatever that page describes. **Always verify against the raw request body**
> (never the re-serialized JSON), or signatures will never match.

---

## 1. Create your Blooio account

1. Go to <https://app.blooio.com> and sign up (a free trial is available without a credit card
   at the time of writing — confirm current terms on <https://blooio.com>).
2. Verify your email and finish onboarding into the dashboard.

## 2. Pick a plan that fits your usage

Blooio's tiers differ on three things that matter for an agent like this:

- **Number type** — *shared* vs *dedicated*. Lower tiers put you on a **shared** sending
  number; a **Dedicated** plan (one number reserved to you) is the higher tier.
- **New contacts per day** — lower tiers cap how many *brand-new* recipients you can start a
  conversation with each day (often a single-digit to low-double-digit number). Replies to
  existing conversations are not the constraint; cold first-contacts are. If your concierge is
  expected to reach out to many new people daily, size up.
- **Contact cards** — sharing a tappable **contact card** (so the user can save your
  business into Contacts, which improves iMessage deliverability and trust) requires a
  **Dedicated** plan. If you set `SHARE_CONTACT_ENABLED=true` in `wrangler.toml`, you need a
  Dedicated plan for that feature to actually work; on a shared number the contact-card call
  will be rejected.

Check the live tiers and caps on **<https://blooio.com/#pricing>** and choose accordingly.
You can start on a lower tier and upgrade — but if you already know you need contact cards or
high new-contact volume, start on Dedicated to avoid re-provisioning a number later.

> **Recommendation for this kit:** if you only want inbound-driven support/sales replies (users
> text you first), a shared-number plan is enough to get going. If you plan to proactively
> message new users or use the contact-card share feature, go Dedicated.

## 3. Provision an iMessage-capable number

1. In the dashboard, open the **Numbers** section.
2. Provision / claim your number for the plan you chose (shared numbers may be assigned
   automatically; a Dedicated plan lets you reserve a line).
3. **Confirm the number is iMessage-enabled.** This kit is built for iMessage (blue-bubble)
   delivery. Blooio numbers are iMessage-capable and will **fall back to SMS/RCS** when the
   recipient isn't on iMessage — that fallback is handled by Blooio, not by your Worker, so
   you don't code anything for it. Just make sure the number shows as iMessage-active in the
   dashboard before testing.

Reference: <https://docs.blooio.com/reference> (Numbers).

> **iMessage vs SMS, briefly.** When a recipient is on Apple/iMessage, messages route over
> iMessage (blue). When they're not, Blooio falls back to SMS (or RCS on Android) over the
> same API. Your Worker sends and receives through one endpoint regardless; routing is
> Blooio's job.

## 4. Get your API key → `BLOOIO_API_KEY`

1. In the dashboard, open **Settings → API Keys** (or the **API** area).
2. Create / copy your **API key**. This is the bearer token the Worker sends as
   `Authorization: Bearer <BLOOIO_API_KEY>`.
3. Store it as a Worker secret (set secrets one at a time — do **not** pipe or loop them):

   ```sh
   wrangler secret put BLOOIO_API_KEY
   # paste the key when prompted
   ```

Reference: <https://docs.blooio.com/authentication>.

## 5. Create the inbound webhook → get `BLOOIO_HMAC_SECRET`

You register the webhook **before** you have the secret — Blooio returns the signing secret as
part of creating the webhook, and it's typically shown **only once**. Copy it immediately.

1. In the dashboard, open **Webhooks** and create a new endpoint (you can also do this via the
   API: `POST /v2/api/webhooks` with your URL — see <https://docs.blooio.com/webhooks>).
2. Set the endpoint URL to your deployed Worker:

   ```
   <WORKER_BASE_URL>/webhooks/blooio
   ```

   Example: `https://my-agent.my-subdomain.workers.dev/webhooks/blooio`
3. Subscribe to **inbound message** events (e.g. the `message.received` / inbound `message`
   event). At minimum you need incoming messages; delivery/read/reaction events are optional.
4. Save. **Copy the signing secret** shown on creation — this is your `BLOOIO_HMAC_SECRET`.
   If you miss it, rotate the secret to reveal a new one (rotating invalidates the old one, so
   update the Worker secret too).
5. Store it as a Worker secret:

   ```sh
   wrangler secret put BLOOIO_HMAC_SECRET
   # paste the webhook signing secret when prompted
   ```

## 6. Confirm the webhook URL points at the right Worker

Your `WORKER_BASE_URL` is the public URL of your deployed Worker — either the
`*.workers.dev` URL Cloudflare gave you, or your custom domain. It must match the
`WORKER_BASE_URL` you set in `wrangler.toml [vars]`.

- Webhook URL registered in Blooio: `<WORKER_BASE_URL>/webhooks/blooio`
- Same base in `wrangler.toml`:

  ```toml
  [vars]
  WORKER_BASE_URL = "https://my-agent.my-subdomain.workers.dev"
  ```

If you later change the Worker's domain, update **both** the Blooio webhook URL and the
`WORKER_BASE_URL` var, then redeploy.

## 7. Verify the secrets are set

```sh
wrangler secret list
```

You should see at least `BLOOIO_API_KEY` and `BLOOIO_HMAC_SECRET` (alongside the other kit
secrets: `ANTHROPIC_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `OPS_BEARER_TOKEN`, and any optional
`SENTRY_DSN` / `SLACK_OPS_WEBHOOK_URL`). Secret **values** are never displayed — only names.

## 8. Smoke-test the round trip

1. From a phone (ideally an iMessage user), text the Blooio number a short message.
2. Watch your Worker logs:

   ```sh
   wrangler tail
   ```

3. You should see the inbound webhook hit `/webhooks/blooio`, pass HMAC verification, and the
   agent generate a reply that Blooio delivers back to your phone.

If the request arrives but **signature verification fails**, the usual causes are: the wrong
secret in `BLOOIO_HMAC_SECRET`, verifying against a re-serialized body instead of the **raw**
bytes, or a webhook-format change on Blooio's side — recheck against
<https://docs.blooio.com/webhooks>. If the request never arrives, the webhook URL is wrong or
points at a stale deployment.

---

## Done when…

- [ ] You have a Blooio account on a plan that fits your new-contact volume (and is **Dedicated**
      if you need contact cards / `SHARE_CONTACT_ENABLED=true`).
- [ ] A number is provisioned and shows as **iMessage-enabled** in the dashboard.
- [ ] `BLOOIO_API_KEY` is set as a Worker secret (`wrangler secret put BLOOIO_API_KEY`).
- [ ] An inbound webhook is registered at `<WORKER_BASE_URL>/webhooks/blooio`, subscribed to
      incoming-message events.
- [ ] `BLOOIO_HMAC_SECRET` (the webhook signing secret) is set as a Worker secret.
- [ ] `WORKER_BASE_URL` in `wrangler.toml` matches the host in the registered webhook URL.
- [ ] `wrangler secret list` shows `BLOOIO_API_KEY` and `BLOOIO_HMAC_SECRET`.
- [ ] You texted the number and saw the inbound webhook verified in `wrangler tail` and got an
      agent reply back on your phone.
