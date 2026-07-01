# Reference Docs

Deep-dive documentation for this iMessage agent starter kit — a stateful
conversational agent built on Cloudflare Workers, the Blooio iMessage API, and
Supabase. These docs explain *how* and *why* the system is built the way it is,
beyond what the top-level README and quickstart cover.

If you just want to get the agent running, start with the project root README.
Come here when you want to understand the architecture, extend the agent, or
adapt it to your own use case.

## Reading order

The docs build on each other. Read them top to bottom the first time through;
after that, treat this as a lookup index.

1. **[ARCHITECTURE.md](./ARCHITECTURE.md)** — Start here. The system from 10,000
   feet: the major components (Worker, iMessage transport, database), how a
   message flows from inbound text to outbound reply, and how state is held
   between turns. Read this before anything else so the rest of the docs have a
   frame to hang on.

2. **[INFRASTRUCTURE.md](./INFRASTRUCTURE.md)** — The platform underneath the
   agent: the Cloudflare Worker, environment variables and secrets, the
   Supabase schema, deployment, and the wiring between services. Read this once
   you understand the shape of the system and want to know where everything
   actually lives and runs.

3. **[BLOOIO-INTEGRATION.md](./BLOOIO-INTEGRATION.md)** — The iMessage
   transport layer: how inbound messages arrive (webhooks), how outbound
   replies are sent, payload shapes, delivery guarantees, and the operational
   gotchas of talking to iMessage through a third-party API.

4. **[AGENT-LOOP.md](./AGENT-LOOP.md)** — The core reasoning loop: how a single
   inbound message is turned into a model call, how tools are defined and
   dispatched, how multi-step turns resolve, and where conversation state is
   loaded and persisted. This is the heart of the agent.

5. **[PROMPT-BEST-PRACTICES.md](./PROMPT-BEST-PRACTICES.md)** — How to write and
   structure the system prompt and tool descriptions that drive the loop:
   instruction layering, tool-use guidance, keeping the agent on-task, and
   patterns that hold up as the prompt grows.

6. **[IMESSAGE-BEST-PRACTICES.md](./IMESSAGE-BEST-PRACTICES.md)** — Conventions
   specific to conversing over iMessage: message length and pacing, handling
   reactions and attachments, threading, read receipts and typing indicators,
   and the UX expectations of a texting interface as opposed to a chat window.

7. **[REFERRAL-ARCHITECTURE.md](./REFERRAL-ARCHITECTURE.md)** — An optional,
   self-contained subsystem: how user-to-user referrals and shareable links are
   modeled, tracked, and credited. Read this only if you need referral
   mechanics; the core agent runs without it.

## How to use these

- **New to the project?** Read 1–4 in order. That's enough to understand the
  system end to end and make your first change.
- **Extending the agent's behavior?** Focus on AGENT-LOOP.md and
  PROMPT-BEST-PRACTICES.md.
- **Tuning the conversational feel?** IMESSAGE-BEST-PRACTICES.md and
  PROMPT-BEST-PRACTICES.md.
- **Operating or deploying?** INFRASTRUCTURE.md and BLOOIO-INTEGRATION.md.
- **Adding referrals?** REFERRAL-ARCHITECTURE.md, last.
