// Per-message-id dedupe for Blooio inbound webhooks. Insert the message_id as a
// PRIMARY KEY; a 409 (PK collision) means we've already seen this delivery.
// Graceful-degrade: any other error treats the event as fresh (process it) so a
// transient DB blip never drops a real message.

import type { Env } from '../env.js';
import { SupabaseError, insertRow } from './supabase.js';
import { log } from './log.js';

export interface DedupeResult {
  /** true = process this event; false = silently ignore (already seen). */
  fresh: boolean;
}

export async function dedupeInbound(env: Env, message_id: string): Promise<DedupeResult> {
  if (!message_id) {
    log.warn('dedupe.no_message_id', {});
    return { fresh: true };
  }
  try {
    await insertRow(env, 'inbound_webhook_events', { message_id });
    return { fresh: true };
  } catch (e) {
    if (e instanceof SupabaseError && e.status === 409) return { fresh: false };
    log.warn('dedupe.unavailable', {
      message_id,
      reason: e instanceof Error ? e.message : String(e),
    });
    return { fresh: true };
  }
}
