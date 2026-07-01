-- Referral add-on (OPT-IN). Apply this ONLY if you set REFERRAL_ENABLED = "true".
-- Adds peer (every-user) + affiliate (influencer) attribution on one set of
-- rails, plus an append-only credit ledger. See reference/REFERRAL-ARCHITECTURE.md.

-- Peer attribution + a denormalized credit balance on the user.
alter table users add column if not exists referral_code          text unique;
alter table users add column if not exists referred_by_user_id    uuid references users(id);
alter table users add column if not exists referral_credit_cents  integer not null default 0;
-- Affiliate attribution (influencer tier).
alter table users add column if not exists affiliate_id           uuid;
alter table users add column if not exists affiliate_attributed_at timestamptz;

-- Operator-created influencer/partner codes (cash-commission tier).
create table if not exists affiliates (
  id               uuid primary key default gen_random_uuid(),
  code             text unique not null,
  name             text,
  email            text,
  phone            text,
  status           text not null default 'active' check (status in ('active', 'paused', 'disabled')),
  commission_cents integer not null default 500,
  created_at       timestamptz not null default now()
);

-- Append-only credit ledger. amount_cents is SIGNED (+ earned, - spent).
create table if not exists referral_credits (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null references users(id),
  amount_cents     integer not null,
  reason           text not null check (reason in ('referrer_reward', 'referee_welcome', 'redeemed')),
  related_user_id  uuid references users(id),
  related_order_id uuid,
  expires_at       timestamptz,
  created_at       timestamptz not null default now()
);
create index if not exists referral_credits_user_idx on referral_credits (user_id);

-- One welcome/reward per referee — the hard idempotency guard for grants.
create unique index if not exists referral_credits_one_reward_per_referee
  on referral_credits (related_user_id)
  where reason in ('referrer_reward', 'referee_welcome');

-- Atomically bump the denormalized balance (the ledger remains canonical).
create or replace function apply_referral_credit_delta(p_user_id uuid, p_delta integer)
returns void language sql as $$
  update users
     set referral_credit_cents = referral_credit_cents + p_delta,
         updated_at = now()
   where id = p_user_id;
$$;
