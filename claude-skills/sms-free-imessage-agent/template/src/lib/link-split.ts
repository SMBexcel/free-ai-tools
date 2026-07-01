// Split a reply of the form "<lead-in text> <single URL>" into two bubbles so
// the URL bubble can carry a rich link preview. Many iMessage gateways (Blooio
// included) only render a link_preview when the message text is EXACTLY one URL.
// Returns null when the text isn't a single-URL-plus-text shape — the caller
// then sends it as one ordinary bubble.

const URL_RE = /https?:\/\/[^\s)]+/g;

export interface LinkSplit {
  /** Bubble 1 — the text with the URL removed (null if nothing meaningful remained). */
  leadIn: string | null;
  /** Bubble 2 — the URL alone (send with a link_preview). */
  url: string;
}

export function splitTrailingLink(text: string): LinkSplit | null {
  const urls = text.match(URL_RE);
  if (!urls || urls.length !== 1) return null; // 0 or 2+ URLs → send as one bubble
  const url = urls[0]!;
  let leadIn = text.replace(url, '');
  leadIn = leadIn
    .replace(/:\s*$/, '')
    .replace(/[\-—–]\s*$/, '')
    .replace(/^\s*[\-—–]\s*/, '')
    .replace(/\s{2,}/g, ' ')
    .trim();
  return { leadIn: leadIn.length > 0 ? leadIn : null, url };
}
