// InboundCoalescer — one Durable Object instance per phone (idFromName(phone)).
// Everything for a phone serializes through it, which makes three things trivial:
//   1. Debounce — buffer burst fragments for 2s, process one coalesced turn.
//   2. Rate limit — an atomic per-phone hourly counter.
//   3. Tapback cooldown — a per-conversation inbound counter + last-fired index.
// The handoff fetch returns immediately; the agent runs in the alarm's scope.

import type { Env } from '../env.js';
import { sendRateLimitReply } from '../lib/blooio.js';
import { log } from '../lib/log.js';

export const DEBOUNCE_MS = 2_000;
export const RATE_LIMIT_PER_HOUR = 100;
const HOUR_MS = 3_600_000;

/** At most one ❤️ tapback per this many inbound messages per conversation. */
export const TAPBACK_COOLDOWN_MESSAGES = 4;
const INBOUND_INDEX_KEY = 'inbound_index';
const LAST_TAPBACK_INDEX_KEY = 'last_tapback_index';

export interface FragmentMeta {
  phone: string;
  external_id: string;
  message_id: string;
  protocol: 'imessage' | 'sms';
}

export interface FragmentRequest {
  text: string;
  meta: FragmentMeta;
}

export interface FragmentResponse {
  buffered: number;
}

interface AgentRunPayload {
  phone: string;
  text: string;
  meta: FragmentMeta;
  inbound_index: number;
  last_tapback_index: number | null;
}

interface AgentRunResponse {
  tapback_fired?: boolean;
}

function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}
function hourBucket(nowMs: number): number {
  return Math.floor(nowMs / HOUR_MS);
}

export class InboundCoalescer implements DurableObject {
  private readonly state: DurableObjectState;
  private readonly env: Env;

  constructor(state: DurableObjectState, env: Env) {
    this.state = state;
    this.env = env;
  }

  async fetch(req: Request): Promise<Response> {
    const url = new URL(req.url);
    if (req.method === 'POST' && url.pathname === '/fragment') {
      const body = (await req.json()) as FragmentRequest;
      return Response.json(await this.fragment(body));
    }
    return new Response('not found', { status: 404 });
  }

  /** Buffer one fragment; arm a single 2s alarm if none pending. */
  async fragment(req: FragmentRequest): Promise<FragmentResponse> {
    const buf = (await this.state.storage.get<string[]>('fragments')) ?? [];
    buf.push(req.text);
    await this.state.storage.put('fragments', buf);

    if (!(await this.state.storage.get<FragmentMeta>('meta'))) {
      await this.state.storage.put('meta', req.meta);
    }
    if ((await this.state.storage.getAlarm()) === null) {
      await this.state.storage.setAlarm(Date.now() + DEBOUNCE_MS);
    }
    return { buffered: buf.length };
  }

  /** Fires 2s after the FIRST fragment of a burst: drain, rate-limit, fan out. */
  async alarm(): Promise<void> {
    const fragments = (await this.state.storage.get<string[]>('fragments')) ?? [];
    const meta = await this.state.storage.get<FragmentMeta>('meta');
    await this.state.storage.delete(['fragments', 'meta']);

    if (!meta || fragments.length === 0) return;
    const text = fragments.join('\n');

    const count = await this.bumpHourlyCount();
    if (count > RATE_LIMIT_PER_HOUR) {
      log.warn('coalescer.rate_limited', { phone: meta.phone, count });
      try {
        await sendRateLimitReply(this.env, meta.phone);
      } catch (e) {
        log.error('coalescer.rate_limit_reply_failed', { phone: meta.phone, reason: errMsg(e) });
      }
      return;
    }

    const inbound_index = await this.bumpInboundIndex();
    const last_tapback_index = (await this.state.storage.get<number>(LAST_TAPBACK_INDEX_KEY)) ?? null;

    const payload: AgentRunPayload = { phone: meta.phone, text, meta, inbound_index, last_tapback_index };
    try {
      const r = await this.env.SELF.fetch(`${this.env.WORKER_BASE_URL}/internal/agent/run`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${this.env.OPS_BEARER_TOKEN}`,
        },
        body: JSON.stringify(payload),
      });
      if (!r.ok) {
        log.error('coalescer.agent_fanout_non_2xx', { phone: meta.phone, status: r.status });
        return;
      }
      let body: AgentRunResponse | null = null;
      try {
        body = (await r.json()) as AgentRunResponse;
      } catch {
        /* non-JSON body — leave the tapback index untouched */
      }
      if (body?.tapback_fired === true) {
        await this.state.storage.put(LAST_TAPBACK_INDEX_KEY, inbound_index);
      }
    } catch (e) {
      log.error('coalescer.agent_fanout_failed', { phone: meta.phone, reason: errMsg(e) });
    }
  }

  private async bumpInboundIndex(): Promise<number> {
    const next = ((await this.state.storage.get<number>(INBOUND_INDEX_KEY)) ?? 0) + 1;
    await this.state.storage.put(INBOUND_INDEX_KEY, next);
    return next;
  }

  /** Atomic per-hour count (single instance per phone = inherent serializability). */
  private async bumpHourlyCount(): Promise<number> {
    const bucket = hourBucket(Date.now());
    const k = `cnt:${bucket}`;
    const cur = (await this.state.storage.get<number>(k)) ?? 0;
    const next = cur + 1;
    await this.state.storage.put(k, next);
    if (cur === 0) await this.state.storage.delete(`cnt:${bucket - 1}`); // DO storage has no TTL
    return next;
  }
}
