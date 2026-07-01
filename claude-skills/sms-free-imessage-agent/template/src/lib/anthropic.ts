// Anthropic SDK wrapper + a prompt-cache helper. The system prompt + tool
// schemas get a `cache_control: ephemeral` block; the first request mints the
// cache and subsequent requests within the 5-min TTL get a large input discount.

import Anthropic from '@anthropic-ai/sdk';
import type { Env } from '../env.js';

export function getAnthropic(env: Env): Anthropic {
  return new Anthropic({ apiKey: env.ANTHROPIC_API_KEY });
}

/** A cache-controlled system-prompt text block. */
export function cachedSystem(text: string): Anthropic.Messages.TextBlockParam {
  return { type: 'text', text, cache_control: { type: 'ephemeral' } };
}

export type { Anthropic };
