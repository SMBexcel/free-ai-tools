-- Core schema for the iMessage agent. Apply in the Supabase SQL editor, via the
-- Supabase CLI, or the Supabase MCP. See setup/SUPABASE-SETUP.md.

create extension if not exists pgcrypto;

-- The person on the other end of the conversation.
create table if not exists users (
  id              uuid primary key default gen_random_uuid(),
  phone           text unique not null,
  display_name    text,
  email           text,
  notes           text,
  last_inbound_at timestamptz,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

-- Every inbound + outbound message, for audit and analytics.
create table if not exists messages (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid references users(id),
  phone          text not null,
  direction      text not null check (direction in ('in', 'out')),
  body           text,
  intent         text,
  external_id    text,
  message_id     text,
  metadata       jsonb,
  created_at     timestamptz not null default now()
);
create index if not exists messages_phone_idx on messages (phone, created_at desc);

-- Agent memory. LangChain-compatible jsonb shape; session_id = E.164 phone.
create table if not exists chat_history (
  id          bigserial primary key,
  session_id  text not null,
  message     jsonb not null,
  created_at  timestamptz not null default now()
);
create index if not exists chat_history_session_idx on chat_history (session_id, created_at desc);

-- Inbound webhook idempotency: a PK collision on message_id = duplicate delivery.
create table if not exists inbound_webhook_events (
  message_id   text primary key,
  received_at  timestamptz not null default now()
);

-- Lightweight audit trail of agent write-tool calls + escalations.
create table if not exists audit_log (
  id          uuid primary key default gen_random_uuid(),
  event       text not null,
  user_id     uuid references users(id),
  metadata    jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now()
);

-- ── EXAMPLE domain tables ───────────────────────────────────────────────────
-- These back the example tools (capture_lead, book_appointment). Replace them
-- with your own domain tables and tools — they're here so the scaffold does
-- something real out of the box.

create table if not exists leads (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid references users(id),
  interest   text,
  name       text,
  email      text,
  notes      text,
  status     text not null default 'new' check (status in ('new', 'qualified', 'won', 'lost')),
  created_at timestamptz not null default now()
);
create index if not exists leads_user_idx on leads (user_id, created_at desc);

create table if not exists bookings (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid references users(id),
  requested_for text,   -- freeform requested time in the user's words
  topic         text,
  status        text not null default 'requested' check (status in ('requested', 'confirmed', 'cancelled')),
  created_at    timestamptz not null default now()
);
create index if not exists bookings_user_idx on bookings (user_id, created_at desc);

-- NOTE: Row Level Security is intentionally NOT enabled — only the Worker, using
-- the Supabase SERVICE ROLE key, ever touches these tables. If you ever expose
-- the anon/client key to a browser or app, enable RLS WITH policies FIRST.
-- See setup/SUPABASE-SETUP.md.
