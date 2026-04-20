/**
 * SHA-256 item key — produces the same 16-char hex prefix as Python's:
 *   hashlib.sha256(text.encode()).hexdigest()[:16]
 * Both encode text as UTF-8 before hashing.
 */
export async function itemKey(text) {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('').slice(0, 16);
}
