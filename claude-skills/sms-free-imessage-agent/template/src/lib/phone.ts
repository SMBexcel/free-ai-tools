// Normalize an inbound identifier to E.164. Defaults a bare 10-digit number to
// US (+1); adjust the default for your market. Used as the chat id everywhere.

export function toE164(input: string): string {
  const raw = String(input ?? '').trim();
  if (raw.startsWith('+')) {
    return '+' + raw.slice(1).replace(/\D/g, '');
  }
  const digits = raw.replace(/\D/g, '');
  if (digits.length === 10) return '+1' + digits; // US default
  if (digits.length === 11 && digits.startsWith('1')) return '+' + digits;
  return '+' + digits; // best effort for already-international numbers
}
