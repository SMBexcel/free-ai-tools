// Webhook signature verification (Stripe-style `t=<unix>,v1=<hex>` scheme,
// which Blooio uses for `x-blooio-signature`). Verify against the RAW request
// bytes — never a re-serialized JSON object.

const REPLAY_TOLERANCE_SEC = 300;
const encoder = new TextEncoder();

export type HMACResult =
  | { ok: true; event: unknown; rawBody: string }
  | { ok: false; reason: string };

async function hmacSha256Hex(secret: string, payload: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );
  const sig = await crypto.subtle.sign('HMAC', key, encoder.encode(payload));
  const bytes = new Uint8Array(sig);
  let hex = '';
  for (let i = 0; i < bytes.length; i++) hex += bytes[i]!.toString(16).padStart(2, '0');
  return hex;
}

function timingSafeEqualHex(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let mismatch = 0;
  for (let i = 0; i < a.length; i++) mismatch |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return mismatch === 0;
}

function parseSignatureHeader(header: string): { t: string; v1: string[] } | null {
  const parts = String(header).split(',').map((p) => p.trim().split('='));
  const t = parts.find((p) => p[0] === 't')?.[1];
  const v1 = parts
    .filter((p) => p[0] === 'v1')
    .map((p) => p[1])
    .filter((v): v is string => typeof v === 'string' && v.length > 0);
  if (!t || v1.length === 0) return null;
  return { t, v1 };
}

/**
 * Verify a `t=...,v1=...` signature header against the raw body using
 * HMAC-SHA256 over `t + "." + rawBody`. 300s replay window; multiple `v1`
 * candidates accepted (key rotation). Returns the parsed event on success.
 */
export async function verifyWebhookSignature(
  rawBody: string,
  sigHeader: string | null,
  secret: string,
): Promise<HMACResult> {
  if (!secret) return { ok: false, reason: 'missing signing secret' };
  if (!sigHeader) return { ok: false, reason: 'missing signature header' };
  if (!rawBody) return { ok: false, reason: 'missing raw body' };

  const parsed = parseSignatureHeader(sigHeader);
  if (!parsed) return { ok: false, reason: 'malformed signature header' };

  const tNum = Number(parsed.t);
  if (!Number.isFinite(tNum)) return { ok: false, reason: 'malformed signature header' };
  const ageSec = Math.abs(Math.floor(Date.now() / 1000) - tNum);
  if (ageSec > REPLAY_TOLERANCE_SEC) return { ok: false, reason: 'event too old (>5min)' };

  const expected = await hmacSha256Hex(secret, parsed.t + '.' + rawBody);
  if (!parsed.v1.some((v) => timingSafeEqualHex(expected, v))) {
    return { ok: false, reason: 'signature mismatch' };
  }

  try {
    return { ok: true, event: JSON.parse(rawBody), rawBody };
  } catch {
    return { ok: false, reason: 'body not valid JSON' };
  }
}

/** Blooio inbound webhook signature verifier (`x-blooio-signature`). */
export function verifyBlooio(
  rawBody: string,
  sigHeader: string | null,
  secret: string,
): Promise<HMACResult> {
  return verifyWebhookSignature(rawBody, sigHeader, secret);
}
