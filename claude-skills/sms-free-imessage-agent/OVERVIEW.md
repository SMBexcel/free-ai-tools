# What this is (plain-English overview)

**Give your business a phone number people can text — and an AI that answers it
24/7, captures leads, books calls, and hands off to a human when it matters.**

You run one guided setup, tell it what your business does, and you get a working
texting assistant on iMessage (and SMS). It feels like texting a real, helpful
person — blue bubbles, typing dots, read receipts, the occasional thumbs-up — but
it never sleeps, never forgets a customer, and answers in seconds.

No app to download for your customers. They just text your number.

---

## What it does for your business

- **Answers instantly, day or night.** Every text gets a helpful reply in
  seconds — nights, weekends, holidays. No missed leads because someone texted at
  9pm.
- **Captures leads automatically.** When someone shows interest, it records who
  they are and what they want, so nothing falls through the cracks.
- **Books calls and appointments.** It offers to get people on your calendar and
  logs the request for your team to confirm.
- **Knows when to get a human.** If someone asks for a person, wants to
  negotiate, or hits something the AI shouldn't handle, it hands off cleanly and
  pings your team.
- **Remembers every customer.** It keeps the history of each conversation and
  what it's learned about each person, so repeat texters feel known — not like
  they're starting over.
- **Turns customers into referrals (optional).** A built-in referral engine gives
  each customer a shareable code, rewards both sides when a friend signs up, and
  blocks the obvious ways people try to game it.
- **Feels genuinely human.** Because it runs on iMessage, it gets the little
  things right — typing indicators, read receipts, tasteful reactions — that make
  a text feel personal instead of robotic.
- **Sounds like *you*.** You set its voice and what it's allowed to do. It's a
  concierge for your business, not a generic chatbot.

---

## Why it's a good deal

- **It runs on infrastructure you own.** Your phone number, your customer data,
  your account — not locked inside someone else's SaaS. You can export, extend, or
  walk away anytime.
- **It's cheap to operate.** The AI and hosting are usage-based and typically cost
  a few cents per conversation or less. Your main recurring cost is your texting
  plan (the phone number). No per-seat "AI agent" subscription.
- **It's a starting point, not a black box.** You (or any developer) can add new
  things it can do — send pricing, check availability, start a trial, look up an
  order — because the whole thing is yours to shape.

---

## Who it's for

Any business that gets inbound interest and hates missing it:

- Local & service businesses (home services, clinics, salons, agencies, trades).
- Anyone running lead-gen who wants speed-to-lead measured in seconds.
- Operators who want a premium, personal customer touch without hiring a 24/7 desk.

If a faster reply or a captured lead is worth money to you, this pays for itself
quickly.

---

## What you need

A one-time setup (about 30–45 minutes) across four services — all have free or
low-cost tiers to start:

| You'll need | For |
|---|---|
| A texting number ([Blooio](https://blooio.com)) | Sending/receiving iMessage & SMS |
| A hosting account ([Cloudflare](https://cloudflare.com)) | Running the assistant (free tier works) |
| A database ([Supabase](https://supabase.com)) | Remembering customers & conversations |
| An AI key ([Anthropic](https://anthropic.com)) | The assistant's "brain" (Claude) |

…plus a developer, or [Claude Code](https://claude.com/claude-code) to run the
setup for you.

---

## How you get it live

1. **Run the setup skill** (`/sms-free-imessage-agent` in Claude Code). It walks
   you through every account and does the technical work for you.
2. **Answer a few questions** — your business name, what you sell, what you want
   the assistant to be able to do.
3. **Text your new number** to confirm it's working — then share it with
   customers.

That's it. From there you can keep teaching it new tricks whenever you want.

---

## The honest fine print

- It's an **AI assistant**, and it's built to say so when a customer genuinely
  asks — it never pretends to be a specific human.
- It only knows what you teach it. Out of the box it answers general questions,
  captures leads, and books calls; anything specific to your business (real
  pricing, live availability, your policies) you plug in during setup.
- Deliverability of iMessage vs SMS and number provisioning are handled by your
  texting provider — check their plan for limits (e.g. how many brand-new
  contacts you can message per day on a starter plan).

---

*Want the technical details? See [DEVELOPER.md](DEVELOPER.md). Want to just build
it? See [README.md](README.md) and run the skill.*
