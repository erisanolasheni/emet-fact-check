/**
 * Build URLs with the Text Fragments directive (#:~:text=…) so Chromium/Safari/WebKit
 * can scroll to and highlight quoted wording on the destination page (Google-style).
 * @see https://wicg.github.io/scroll-to-text-fragment/
 */

const EXCERPT_MIN = 8;
const EXCERPT_MAX = 360;

/** Normalize whitespace and trim to a stable quoted span (excerpt is usually from the page). */
export function excerptForTextFragment(raw: string | null | undefined): string | null {
  if (!raw?.trim()) return null;
  const compact = raw.replace(/\s+/g, " ").trim();
  if (compact.length < EXCERPT_MIN) return null;
  if (compact.length <= EXCERPT_MAX) return compact;
  const head = compact.slice(0, EXCERPT_MAX);
  const lastBreak = Math.max(head.lastIndexOf(". "), head.lastIndexOf("! "), head.lastIndexOf("? "));
  if (lastBreak > EXCERPT_MAX * 0.45) return head.slice(0, lastBreak + 1).trim();
  const sp = head.lastIndexOf(" ");
  return (sp > EXCERPT_MAX * 0.55 ? head.slice(0, sp) : head).trim();
}

/**
 * Returns `baseUrl` with `#:~:text=…` so the browser jumps to the passage when the tab loads.
 * Any existing hash is replaced. If excerpt is missing/too short, returns `baseUrl` unchanged.
 */
export function withTextFragmentDirective(baseUrl: string, excerpt: string | null | undefined): string {
  const text = excerptForTextFragment(excerpt ?? "");
  if (!text) return baseUrl;

  try {
    const url = new URL(baseUrl);
    url.hash = `:~:text=${encodeURIComponent(text)}`;
    return url.href;
  } catch {
    return baseUrl;
  }
}