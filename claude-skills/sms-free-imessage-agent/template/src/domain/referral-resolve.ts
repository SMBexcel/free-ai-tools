// Referral add-on — the ONE shared attribution path for both the peer
// (every-user) and affiliate (influencer) namespaces. Resolves a code, applies
// the self-referral block + first-touch-wins, writes attribution, and (for a
// fresh PEER referral) grants the referee's welcome credit at attribution time.
// Never throws — attribution is best-effort and must never block a turn.

import type { Env } from '../env.js';
import { REFEREE_WELCOME_CENTS, creditExpiryDate, isValidReferralCode } from './referral.js';
import { log } from '../lib/log.js';
import { insertRow, rpcCall, selectOne, updateRows } from '../lib/supabase.js';

export type ReferralKind = 'affiliate' | 'peer';

export type ResolveOutcome =
  | { kind: 'affiliate'; affiliate_id: string; code: string }
  | { kind: 'peer'; referrer_user_id: string; code: string }
  | { kind: 'none'; reason: 'invalid_code' | 'not_found' | 'inactive_affiliate' | 'self_referral' };

interface AffiliateRow { id?: string; phone?: string | null; email?: string | null; status?: string | null; }
interface PeerUserRow { id?: string; phone?: string | null; email?: string | null; }

export interface ResolveContext {
  refereePhone?: string | null;
  refereeEmail?: string | null;
  refereeUserId?: string | null;
}

export async function resolveReferralCode(
  env: Env,
  rawCode: string,
  refCtx: ResolveContext,
): Promise<ResolveOutcome> {
  const code = typeof rawCode === 'string' ? rawCode.trim().toUpperCase() : '';
  if (!isValidReferralCode(code)) return { kind: 'none', reason: 'invalid_code' };
  const enc = encodeURIComponent(code);
  const refPhone = norm(refCtx.refereePhone);
  const refEmail = normEmail(refCtx.refereeEmail);

  // 1. Affiliate namespace first (operator/influencer codes).
  try {
    const aff = await selectOne<AffiliateRow>(
      env,
      'affiliates',
      `?code=eq.${enc}&select=id,phone,email,status&limit=1`,
    );
    if (aff?.id) {
      if (aff.status !== 'active') return { kind: 'none', reason: 'inactive_affiliate' };
      if (isSelfReferral(refPhone, refEmail, norm(aff.phone), normEmail(aff.email))) {
        return { kind: 'none', reason: 'self_referral' };
      }
      return { kind: 'affiliate', affiliate_id: aff.id, code };
    }
  } catch (e) {
    log.warn('referral.resolve_affiliate_failed', { code, reason: errMsg(e) });
  }

  // 2. Peer namespace (every-user referral codes).
  try {
    const peer = await selectOne<PeerUserRow>(
      env,
      'users',
      `?referral_code=eq.${enc}&select=id,phone,email&limit=1`,
    );
    if (peer?.id) {
      if (refCtx.refereeUserId && peer.id === refCtx.refereeUserId) {
        return { kind: 'none', reason: 'self_referral' };
      }
      if (isSelfReferral(refPhone, refEmail, norm(peer.phone), normEmail(peer.email))) {
        return { kind: 'none', reason: 'self_referral' };
      }
      return { kind: 'peer', referrer_user_id: peer.id, code };
    }
  } catch (e) {
    log.warn('referral.resolve_peer_failed', { code, reason: errMsg(e) });
  }

  return { kind: 'none', reason: 'not_found' };
}

export interface AttributeResult {
  ok: boolean;
  kind?: ReferralKind;
  affiliate_id?: string;
  referrer_user_id?: string;
  already_attributed?: boolean;
  reason?: string;
}

interface RefereeAttribRow {
  affiliate_id?: string | null;
  referred_by_user_id?: string | null;
}

/**
 * Resolve and, if it lands, WRITE first-touch attribution onto the referee.
 * First-touch-wins across BOTH namespaces; a fresh peer attribution also grants
 * the referee's welcome credit. Best-effort: never throws.
 */
export async function resolveAndAttribute(
  env: Env,
  rawCode: string,
  refereeUserId: string,
  refCtx: Omit<ResolveContext, 'refereeUserId'>,
): Promise<AttributeResult> {
  if (!refereeUserId) return { ok: false, reason: 'no_user' };

  let referee: RefereeAttribRow | null = null;
  try {
    referee = await selectOne<RefereeAttribRow>(
      env,
      'users',
      `?id=eq.${encodeURIComponent(refereeUserId)}&select=affiliate_id,referred_by_user_id&limit=1`,
    );
  } catch (e) {
    log.warn('referral.attribute_fetch_failed', { user_id: refereeUserId, reason: errMsg(e) });
    return { ok: false, reason: 'referee_read_failed' };
  }
  if (!referee) return { ok: false, reason: 'referee_not_found' };

  if (referee.affiliate_id) {
    return { ok: true, kind: 'affiliate', affiliate_id: referee.affiliate_id, already_attributed: true };
  }
  if (referee.referred_by_user_id) {
    return { ok: true, kind: 'peer', referrer_user_id: referee.referred_by_user_id, already_attributed: true };
  }

  const outcome = await resolveReferralCode(env, rawCode, { ...refCtx, refereeUserId });
  if (outcome.kind === 'none') return { ok: false, reason: outcome.reason };

  if (outcome.kind === 'affiliate') {
    try {
      await updateRows(
        env,
        'users',
        `id=eq.${encodeURIComponent(refereeUserId)}&affiliate_id=is.null&referred_by_user_id=is.null`,
        { affiliate_id: outcome.affiliate_id, affiliate_attributed_at: new Date().toISOString() },
      );
    } catch (e) {
      log.warn('referral.attribute_affiliate_write_failed', { user_id: refereeUserId, reason: errMsg(e) });
      return { ok: false, reason: 'write_failed' };
    }
    log.info('referral.attributed', { user_id: refereeUserId, kind: 'affiliate' });
    return { ok: true, kind: 'affiliate', affiliate_id: outcome.affiliate_id };
  }

  // Peer attribution.
  try {
    await updateRows(
      env,
      'users',
      `id=eq.${encodeURIComponent(refereeUserId)}&affiliate_id=is.null&referred_by_user_id=is.null`,
      { referred_by_user_id: outcome.referrer_user_id },
    );
  } catch (e) {
    log.warn('referral.attribute_peer_write_failed', { user_id: refereeUserId, reason: errMsg(e) });
    return { ok: false, reason: 'write_failed' };
  }
  log.info('referral.attributed', { user_id: refereeUserId, kind: 'peer' });

  // Grant the referee's welcome credit now (the acquisition incentive). The
  // REFERRER's reward fires later, on the referee's first conversion/paid action
  // (your own pipeline) — that's the anti-farming gate.
  await grantRefereeWelcome(env, refereeUserId);
  return { ok: true, kind: 'peer', referrer_user_id: outcome.referrer_user_id };
}

/** Insert one welcome-credit ledger row + bump the denormalized balance. Idempotent-ish, fail-open. */
async function grantRefereeWelcome(env: Env, refereeUserId: string): Promise<void> {
  try {
    const prior = await selectOne<{ id?: string }>(
      env,
      'referral_credits',
      `?related_user_id=eq.${encodeURIComponent(refereeUserId)}&reason=in.(referrer_reward,referee_welcome)&select=id&limit=1`,
    );
    if (prior?.id) return;

    await insertRow(env, 'referral_credits', {
      user_id: refereeUserId,
      amount_cents: REFEREE_WELCOME_CENTS,
      reason: 'referee_welcome',
      related_user_id: refereeUserId,
      related_order_id: null,
      expires_at: creditExpiryDate(new Date()).toISOString(),
    });
    await rpcCall(env, 'apply_referral_credit_delta', {
      p_user_id: refereeUserId,
      p_delta: REFEREE_WELCOME_CENTS,
    });
    log.info('referral.referee_welcome_granted', { user_id: refereeUserId });
  } catch (e) {
    log.warn('referral.referee_welcome_failed', { user_id: refereeUserId, reason: errMsg(e) });
  }
}

// ── helpers ─────────────────────────────────────────────────────────────────

function isSelfReferral(
  refereePhone: string | null,
  refereeEmail: string | null,
  referrerPhone: string | null,
  referrerEmail: string | null,
): boolean {
  if (refereePhone && referrerPhone && refereePhone === referrerPhone) return true;
  if (refereeEmail && referrerEmail && refereeEmail === referrerEmail) return true;
  return false;
}
function norm(v: string | null | undefined): string | null {
  if (typeof v !== 'string') return null;
  const t = v.trim();
  return t === '' ? null : t;
}
function normEmail(v: string | null | undefined): string | null {
  const n = norm(v);
  return n ? n.toLowerCase() : null;
}
function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}
