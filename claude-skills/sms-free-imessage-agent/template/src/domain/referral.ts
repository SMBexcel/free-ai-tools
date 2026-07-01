// Referral add-on — PURE domain logic (no IO, no Date.now(): callers pass `now`,
// the one entropy source accepts a stub). Opt-in: only wired when
// REFERRAL_ENABLED === 'true' and migration 0002_referral.sql is applied.
//
// Two referrer types on one set of rails:
//   - peer (every user): earns ACCOUNT CREDIT.
//   - affiliate (influencer): earns a CASH commission (you wire your own payout).
// See reference/REFERRAL-ARCHITECTURE.md for the full design.

/** Peer referrer reward, in cents (granted on the referee's first conversion). */
export const REFERRER_REWARD_CENTS = 500;
/** Referee welcome credit, in cents (granted at attribution; discounts order #1). */
export const REFEREE_WELCOME_CENTS = 500;
/** Peer credits expire this many months after they're granted. */
export const CREDIT_EXPIRY_MONTHS = 12;
/** Most payment processors reject charges below ~50¢. */
export const MIN_CHARGE_CENTS = 50;

export const CREDIT_REASONS = ['referrer_reward', 'referee_welcome', 'redeemed'] as const;
export type CreditReason = (typeof CREDIT_REASONS)[number];

export type RandomBytes = (len: number) => Uint8Array;
const defaultRandomBytes: RandomBytes = (len) => {
  const buf = new Uint8Array(len);
  crypto.getRandomValues(buf);
  return buf;
};

// Crockford-minus-confusables (no 0/O, 1/I/L, U) so a code read aloud or off a
// screen doesn't get mistyped. 30 symbols.
const SUFFIX_ALPHABET = 'ABCDEFGHJKMNPQRSTVWXYZ23456789';
const SUFFIX_LEN = 4;

/** First name token → uppercase A–Z slug, capped at 8; 'FRIEND' if empty. */
export function firstNameSlug(displayName: string | null | undefined): string {
  if (typeof displayName !== 'string') return 'FRIEND';
  const firstToken = displayName.trim().split(/\s+/)[0] ?? '';
  const letters = firstToken.toUpperCase().replace(/[^A-Z]/g, '');
  return letters.length === 0 ? 'FRIEND' : letters.slice(0, 8);
}

/** 4-char suffix with rejection sampling to avoid modulo bias. */
export function randomSuffix(randomBytes: RandomBytes = defaultRandomBytes): string {
  const out: string[] = [];
  const bytes = randomBytes(SUFFIX_LEN * 4);
  const LIMIT = 240; // largest multiple of 30 <= 256
  for (let i = 0; i < bytes.length && out.length < SUFFIX_LEN; i++) {
    const b = bytes[i]!;
    if (b >= LIMIT) continue;
    out.push(SUFFIX_ALPHABET[b % SUFFIX_ALPHABET.length]!);
  }
  while (out.length < SUFFIX_LEN) {
    const extra = randomBytes(1)[0]!;
    out.push(SUFFIX_ALPHABET[extra % SUFFIX_ALPHABET.length]!);
  }
  return out.join('');
}

/** Readable code: `<SLUG>-<4 random>`, e.g. "DAVE-4F2A". */
export function buildReferralCode(
  displayName: string | null | undefined,
  randomBytes: RandomBytes = defaultRandomBytes,
): string {
  return `${firstNameSlug(displayName)}-${randomSuffix(randomBytes)}`;
}

/** Shape gate before a DB lookup (the table lookup is the real authenticity gate). */
export function isValidReferralCode(code: string): boolean {
  if (typeof code !== 'string') return false;
  if (code.length < 4 || code.length > 24) return false;
  return /^[A-Z0-9]+(-[A-Z0-9]+)*$/.test(code);
}

/** now + 12 months (calendar arithmetic). */
export function creditExpiryDate(now: Date): Date {
  const d = new Date(now.getTime());
  d.setUTCMonth(d.getUTCMonth() + CREDIT_EXPIRY_MONTHS);
  return d;
}

export interface ReferralCreditRow {
  amount_cents: number;
  reason: string;
  expires_at: string | null;
  created_at: string;
}

/**
 * True available balance from the ledger: FIFO consumption + 12-month expiry.
 * Pure + idempotent — depends only on earned rows, 'redeemed' debits, and `now`.
 */
export function computeAvailableReferralCents(rows: ReferralCreditRow[], now: Date): number {
  if (!Array.isArray(rows) || rows.length === 0) return 0;
  const nowMs = now.getTime();
  const amt = (r: ReferralCreditRow): number => (Number.isFinite(r.amount_cents) ? r.amount_cents : 0);

  const earned = rows
    .filter((r) => amt(r) > 0)
    .map((r, i) => ({ r, i }))
    .sort((a, b) => {
      const ta = Date.parse(a.r.created_at);
      const tb = Date.parse(b.r.created_at);
      const va = Number.isNaN(ta) ? 0 : ta;
      const vb = Number.isNaN(tb) ? 0 : tb;
      return va !== vb ? va - vb : a.i - b.i;
    })
    .map((x) => x.r);

  let remainingToSpend = 0;
  for (const r of rows) {
    const a = amt(r);
    if (a < 0 && r.reason === 'redeemed') remainingToSpend += -a;
  }

  let available = 0;
  for (const g of earned) {
    const grant = amt(g);
    const spent = Math.min(grant, remainingToSpend);
    remainingToSpend -= spent;
    const unspent = grant - spent;
    if (unspent <= 0) continue;
    const expired =
      g.expires_at != null &&
      !Number.isNaN(Date.parse(g.expires_at)) &&
      Date.parse(g.expires_at) < nowMs;
    if (!expired) available += unspent;
  }
  return available > 0 ? available : 0;
}

export interface RedemptionInput {
  availableCreditCents: number;
  orderTotalCents: number;
  minChargeCents?: number;
}
export interface RedemptionResult {
  appliedCents: number;
  chargeCents: number;
  remainingCreditCents: number;
}

/**
 * Apply min(credit, total) against a charge, never leaving a charge strictly
 * between 0 and the processor minimum. Never throws (payment-critical).
 */
export function computeRedemption(input: RedemptionInput): RedemptionResult {
  const floor =
    Number.isFinite(input.minChargeCents) && (input.minChargeCents ?? 0) >= 0
      ? Math.floor(input.minChargeCents as number)
      : MIN_CHARGE_CENTS;
  const total =
    Number.isFinite(input.orderTotalCents) && input.orderTotalCents > 0
      ? Math.floor(input.orderTotalCents)
      : 0;
  const credit =
    Number.isFinite(input.availableCreditCents) && input.availableCreditCents > 0
      ? Math.floor(input.availableCreditCents)
      : 0;

  if (total === 0 || credit === 0) {
    return { appliedCents: 0, chargeCents: total, remainingCreditCents: credit };
  }
  let applied = Math.min(credit, total);
  let charge = total - applied;
  if (charge > 0 && charge < floor) {
    if (total >= floor) {
      charge = floor;
      applied = total - floor;
    } else {
      charge = 0;
      applied = total;
    }
  }
  return { appliedCents: applied, chargeCents: charge, remainingCreditCents: credit - applied };
}
