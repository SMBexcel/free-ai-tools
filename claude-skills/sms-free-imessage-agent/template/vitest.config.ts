import { defineConfig } from 'vitest/config';

// The bundled tests cover pure helpers (HMAC verify, link splitting) that run
// fine under plain Node — no Workers runtime needed. Add @cloudflare/vitest-pool-workers
// if you start testing code that needs real bindings (DO storage, etc.).
export default defineConfig({
  test: {
    environment: 'node',
    include: ['tests/**/*.test.ts'],
  },
});
