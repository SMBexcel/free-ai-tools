import { describe, it, expect } from 'vitest';
import { splitTrailingLink } from '../src/lib/link-split.js';

describe('splitTrailingLink', () => {
  it('splits "text + single URL" into two bubbles', () => {
    const r = splitTrailingLink('tap to confirm: https://example.com/checkout/abc');
    expect(r).not.toBeNull();
    expect(r!.url).toBe('https://example.com/checkout/abc');
    expect(r!.leadIn).toBe('tap to confirm');
  });

  it('returns null when there is no URL (send as one bubble)', () => {
    expect(splitTrailingLink('just a normal message')).toBeNull();
  });

  it('returns null when there are two URLs', () => {
    expect(splitTrailingLink('see https://a.com and https://b.com')).toBeNull();
  });

  it('yields a null leadIn for a URL-only message', () => {
    const r = splitTrailingLink('https://example.com/x');
    expect(r).not.toBeNull();
    expect(r!.leadIn).toBeNull();
  });
});
