import { describe, it, expect } from 'vitest';
import { verifyWebhookSignature } from '../src/lib/hmac.js';

async function sign(secret: string, t: number, body: string): Promise<string> {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw',
    enc.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode(`${t}.${body}`));
  const bytes = new Uint8Array(sig);
  let hex = '';
  for (const b of bytes) hex += b.toString(16).padStart(2, '0');
  return hex;
}

describe('verifyWebhookSignature', () => {
  const secret = 'test-secret';
  const body = JSON.stringify({ event: 'message.received', text: 'hi' });

  it('accepts a valid signature', async () => {
    const t = Math.floor(Date.now() / 1000);
    const v1 = await sign(secret, t, body);
    const res = await verifyWebhookSignature(body, `t=${t},v1=${v1}`, secret);
    expect(res.ok).toBe(true);
  });

  it('rejects a tampered body', async () => {
    const t = Math.floor(Date.now() / 1000);
    const v1 = await sign(secret, t, body);
    const res = await verifyWebhookSignature(body + 'x', `t=${t},v1=${v1}`, secret);
    expect(res.ok).toBe(false);
  });

  it('rejects an old timestamp', async () => {
    const t = Math.floor(Date.now() / 1000) - 10_000;
    const v1 = await sign(secret, t, body);
    const res = await verifyWebhookSignature(body, `t=${t},v1=${v1}`, secret);
    expect(res.ok).toBe(false);
  });

  it('rejects a missing header', async () => {
    const res = await verifyWebhookSignature(body, null, secret);
    expect(res.ok).toBe(false);
  });
});
