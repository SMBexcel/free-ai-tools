// Referral add-on — issue a unique referral code to a user (idempotent). Retries
// on collision across BOTH the users.referral_code and affiliates.code
// namespaces; the users.referral_code UNIQUE constraint is the final guard.

import type { Env } from '../env.js';
import { buildReferralCode } from './referral.js';
import { selectOne, updateRows } from '../lib/supabase.js';
import { log } from '../lib/log.js';

async function codeTaken(env: Env, code: string): Promise<boolean> {
  const enc = encodeURIComponent(code);
  try {
    if (await selectOne(env, 'users', `?referral_code=eq.${enc}&select=id&limit=1`)) return true;
  } catch {
    /* table/transient error — assume free, the UNIQUE constraint is the backstop */
  }
  try {
    if (await selectOne(env, 'affiliates', `?code=eq.${enc}&select=id&limit=1`)) return true;
  } catch {
    /* affiliates table may not exist if you didn't apply 0002 — fine */
  }
  return false;
}

export async function ensureReferralCode(
  env: Env,
  userId: string,
  displayName: string | null,
): Promise<string | null> {
  const existing = await selectOne<{ referral_code?: string | null }>(
    env,
    'users',
    `?id=eq.${encodeURIComponent(userId)}&select=referral_code&limit=1`,
  ).catch(() => null);
  if (existing?.referral_code) return existing.referral_code;

  for (let attempt = 0; attempt < 5; attempt++) {
    const code = buildReferralCode(displayName);
    if (await codeTaken(env, code)) continue;
    try {
      await updateRows(
        env,
        'users',
        `id=eq.${encodeURIComponent(userId)}&referral_code=is.null`,
        { referral_code: code },
      );
      return code;
    } catch (e) {
      log.warn('referral.issue_write_failed', { reason: e instanceof Error ? e.message : String(e) });
    }
  }
  return null;
}
