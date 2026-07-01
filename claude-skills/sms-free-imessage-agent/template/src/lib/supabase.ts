// Thin PostgREST client over Supabase, using the SERVICE ROLE key (server-only).
// Covers the small surface the agent needs: select / insert / upsert / update /
// rpc, plus a message-log helper. A 409 surfaces as SupabaseError.status === 409
// (used by the inbound dedupe gate).

import type { Env } from '../env.js';

export class SupabaseError extends Error {
  override readonly name = 'SupabaseError';
  constructor(
    readonly status: number,
    readonly bodyText: string,
    readonly method: string,
    readonly path: string,
  ) {
    super(`Supabase ${method} ${path} -> ${status}${bodyText ? ': ' + bodyText.slice(0, 240) : ''}`);
  }
}

function rest(env: Env): string {
  return `${env.SUPABASE_URL}/rest/v1`;
}

function headers(env: Env, extra?: Record<string, string>): Record<string, string> {
  return {
    apikey: env.SUPABASE_SERVICE_ROLE_KEY,
    Authorization: `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`,
    'Content-Type': 'application/json',
    ...(extra ?? {}),
  };
}

export async function selectRows<T>(env: Env, table: string, query = ''): Promise<T[]> {
  const path = `/${table}${query}`;
  const r = await fetch(rest(env) + path, { headers: headers(env) });
  if (!r.ok) throw new SupabaseError(r.status, await r.text().catch(() => ''), 'GET', path);
  return (await r.json()) as T[];
}

export async function selectOne<T>(env: Env, table: string, query = ''): Promise<T | null> {
  const rows = await selectRows<T>(env, table, query);
  return rows[0] ?? null;
}

export async function insertRow<T = unknown>(
  env: Env,
  table: string,
  row: Record<string, unknown>,
  opts?: { returning?: boolean },
): Promise<T | null> {
  const path = `/${table}`;
  const prefer = opts?.returning ? 'return=representation' : 'return=minimal';
  const r = await fetch(rest(env) + path, {
    method: 'POST',
    headers: headers(env, { Prefer: prefer }),
    body: JSON.stringify(row),
  });
  if (!r.ok) throw new SupabaseError(r.status, await r.text().catch(() => ''), 'POST', path);
  if (!opts?.returning) return null;
  const rows = (await r.json()) as T[];
  return rows[0] ?? null;
}

export async function upsertRow<T = unknown>(
  env: Env,
  table: string,
  row: Record<string, unknown>,
  opts: { onConflict: string; returning?: boolean },
): Promise<T | null> {
  const path = `/${table}?on_conflict=${encodeURIComponent(opts.onConflict)}`;
  const prefer = `resolution=merge-duplicates,${opts.returning ? 'return=representation' : 'return=minimal'}`;
  const r = await fetch(rest(env) + path, {
    method: 'POST',
    headers: headers(env, { Prefer: prefer }),
    body: JSON.stringify(row),
  });
  if (!r.ok) throw new SupabaseError(r.status, await r.text().catch(() => ''), 'POST', path);
  if (!opts.returning) return null;
  const rows = (await r.json()) as T[];
  return rows[0] ?? null;
}

export async function updateRows<T = unknown>(
  env: Env,
  table: string,
  filter: string,
  patch: Record<string, unknown>,
  opts?: { returning?: boolean },
): Promise<T[]> {
  const path = `/${table}?${filter}`;
  const prefer = opts?.returning ? 'return=representation' : 'return=minimal';
  const r = await fetch(rest(env) + path, {
    method: 'PATCH',
    headers: headers(env, { Prefer: prefer }),
    body: JSON.stringify(patch),
  });
  if (!r.ok) throw new SupabaseError(r.status, await r.text().catch(() => ''), 'PATCH', path);
  if (!opts?.returning) return [];
  return (await r.json()) as T[];
}

export async function rpcCall<T = unknown>(
  env: Env,
  fn: string,
  args: Record<string, unknown>,
): Promise<T> {
  const path = `/rpc/${fn}`;
  const r = await fetch(rest(env) + path, {
    method: 'POST',
    headers: headers(env),
    body: JSON.stringify(args),
  });
  if (!r.ok) throw new SupabaseError(r.status, await r.text().catch(() => ''), 'POST', path);
  const text = await r.text();
  return (text ? JSON.parse(text) : null) as T;
}

// ── Message log helper ─────────────────────────────────────────────────────

export interface MessageRow {
  user_id?: string | null;
  phone: string;
  direction: 'in' | 'out';
  body?: string | null;
  intent?: string | null;
  external_id?: string | null;
  message_id?: string | null;
  metadata?: Record<string, unknown> | null;
}

export async function insertMessage(env: Env, m: MessageRow): Promise<void> {
  await insertRow(env, 'messages', {
    user_id: m.user_id ?? null,
    phone: m.phone,
    direction: m.direction,
    body: m.body ?? null,
    intent: m.intent ?? null,
    external_id: m.external_id ?? null,
    message_id: m.message_id ?? null,
    metadata: m.metadata ?? null,
  });
}
