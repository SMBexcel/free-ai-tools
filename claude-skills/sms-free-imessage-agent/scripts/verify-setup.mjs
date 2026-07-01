#!/usr/bin/env node
// Post-deploy smoke check. Hits the deployed Worker and confirms the basics.
//
//   node scripts/verify-setup.mjs https://your-worker.your-subdomain.workers.dev
//
// Checks:
//   1. GET  /healthz            → { ok: true }
//   2. POST /webhooks/blooio    → 401 (unsigned, so the HMAC gate must reject it)

const base = (process.argv[2] || process.env.WORKER_BASE_URL || '').replace(/\/+$/, '');
if (!base) {
  console.error('Usage: node scripts/verify-setup.mjs <WORKER_BASE_URL>');
  process.exit(1);
}

let failures = 0;

async function main() {
  // 1. healthz
  try {
    const r = await fetch(`${base}/healthz`);
    const body = await r.json().catch(() => ({}));
    const ok = r.ok && body && body.ok === true;
    console.log(`healthz: ${r.status} ${JSON.stringify(body)} ${ok ? '✓' : '✗'}`);
    if (!ok) failures++;
  } catch (e) {
    console.log(`healthz: ERROR ${String(e)} ✗`);
    failures++;
  }

  // 2. unsigned webhook → must be rejected with 401
  try {
    const r = await fetch(`${base}/webhooks/blooio`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
    const ok = r.status === 401;
    console.log(`webhook (unsigned): ${r.status} ${ok ? '✓ HMAC gate active' : '✗ expected 401'}`);
    if (!ok) failures++;
  } catch (e) {
    console.log(`webhook: ERROR ${String(e)} ✗`);
    failures++;
  }

  console.log('');
  if (failures === 0) {
    console.log('All checks passed. Now register the Blooio webhook and send a real text.');
  } else {
    console.log(`${failures} check(s) failed — see setup/CLOUDFLARE-SETUP.md and setup/BLOOIO-SETUP.md.`);
    process.exit(1);
  }
}

main();
