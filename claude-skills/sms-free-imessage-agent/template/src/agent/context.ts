// Pre-agent context assembly. Fetches the user row + recent domain state and
// serializes it (plus the inbound message) into ONE structured user-turn string
// the model reads.
//
// >>> THIS IS YOUR MAIN EXTENSION POINT <<<
// The example surfaces recent `leads` and `bookings`. Swap those for your domain
// state (open orders, tickets, account status...). Because the model is handed
// everything it needs up front, it never needs read/lookup tools and can't
// hallucinate a lookup — see reference/PROMPT-BEST-PRACTICES.md. The domain reads
// are fail-soft (a missing table yields [] rather than breaking the turn).

import type { Env } from '../env.js';
import { selectOne, selectRows } from '../lib/supabase.js';

export type UserRow = Record<string, unknown> & {
  id?: string;
  display_name?: string | null;
};
export type LeadRow = Record<string, unknown> & { id?: string };
export type BookingRow = Record<string, unknown> & { id?: string };

export interface FetchedContext {
  user: UserRow;
  leads: LeadRow[];
  bookings: BookingRow[];
}

export interface AgentContext {
  phone: string;
  text: string;
  user: UserRow;
  leads: LeadRow[];
  bookings: BookingRow[];
  contextString: string;
  user_id: string | null;
  user_exists: boolean;
}

export async function fetchUser(env: Env, phone: string): Promise<UserRow> {
  const user = await selectOne<UserRow>(env, 'users', `?phone=eq.${encodeURIComponent(phone)}&limit=1`);
  return user ?? {};
}

/** User row first, then recent domain state in parallel (fail-soft). */
export async function fetchAgentContext(env: Env, phone: string): Promise<FetchedContext> {
  const user = await fetchUser(env, phone);
  const userId = typeof user.id === 'string' ? user.id : null;
  if (!userId) return { user, leads: [], bookings: [] };

  const filter = `user_id=eq.${encodeURIComponent(userId)}`;
  const [leads, bookings] = await Promise.all([
    selectRows<LeadRow>(env, 'leads', `?${filter}&order=created_at.desc&limit=5`).catch(() => [] as LeadRow[]),
    selectRows<BookingRow>(env, 'bookings', `?${filter}&order=created_at.desc&limit=5`).catch(() => [] as BookingRow[]),
  ]);
  return { user, leads, bookings };
}

export function buildContext(input: {
  phone: string;
  text: string;
  user: UserRow;
  leads?: LeadRow[];
  bookings?: BookingRow[];
}): AgentContext {
  const user = input.user ?? {};
  const leads = input.leads ?? [];
  const bookings = input.bookings ?? [];

  const contextString = [
    'Inbound from: ' + input.phone,
    '',
    '# User',
    JSON.stringify(user, null, 2),
    '',
    `# Recent leads (${leads.length})`,
    JSON.stringify(leads, null, 2),
    '',
    `# Bookings (${bookings.length})`,
    JSON.stringify(bookings, null, 2),
    '',
    '# Message',
    input.text,
  ].join('\n');

  const user_id = typeof user.id === 'string' ? user.id : null;
  return {
    phone: input.phone,
    text: input.text,
    user,
    leads,
    bookings,
    contextString,
    user_id,
    user_exists: !!user_id,
  };
}
