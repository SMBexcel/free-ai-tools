// Conversation memory — a windowed chat log keyed by the E.164 phone
// (session_id). Stored in a LangChain-compatible jsonb shape so you can swap in
// other tooling later without a data migration.

import type { Env } from '../env.js';
import { insertRow, selectRows } from '../lib/supabase.js';

const WINDOW = 6;

interface ChatHistoryRow {
  id?: number;
  session_id: string;
  message: { type: 'human' | 'ai'; data: { content: string } };
  created_at?: string;
}

export interface MemoryMessage {
  role: 'user' | 'assistant';
  content: string;
}

/** Most recent WINDOW turns for a phone, oldest-first. */
export async function loadMemory(env: Env, phone: string): Promise<MemoryMessage[]> {
  const rows = await selectRows<ChatHistoryRow>(
    env,
    'chat_history',
    `?session_id=eq.${encodeURIComponent(phone)}&order=created_at.desc&limit=${WINDOW}`,
  );
  return rows
    .slice()
    .reverse()
    .map((r) => ({
      role: (r.message?.type === 'human' ? 'user' : 'assistant') as 'user' | 'assistant',
      content: r.message?.data?.content ?? '',
    }))
    .filter((m) => m.content.length > 0);
}

/** Append a pre-seeded AI turn (e.g. a welcome bubble) so it shows in context. */
export function appendAITurn(env: Env, phone: string, content: string): Promise<void> {
  return appendTurn(env, phone, 'ai', content);
}

/**
 * Append the human turn then the AI reply, sequentially, so the human row always
 * gets the lower id / earlier timestamp (a parallel race could invert them).
 */
export async function appendTurns(env: Env, phone: string, human: string, ai: string): Promise<void> {
  await appendTurn(env, phone, 'human', human);
  await appendTurn(env, phone, 'ai', ai);
}

async function appendTurn(env: Env, phone: string, type: 'human' | 'ai', content: string): Promise<void> {
  if (!content) return;
  await insertRow(env, 'chat_history', {
    session_id: phone,
    message: { type, data: { content } },
  });
}
