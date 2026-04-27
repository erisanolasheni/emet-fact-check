/** Google favicon service — same as ReferenceCard. */

export function faviconUrl(hostname: string): string {
  const h = hostname.replace(/^www\./, "");
  return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(h)}&sz=32`;
}
