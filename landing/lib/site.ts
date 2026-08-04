/**
 * Where this copy of the site lives.
 *
 * Absolute URLs are needed in three places that cannot work without one: the
 * sitemap, robots, and the image a link preview loads. Relative paths are fine
 * for a browser and useless to Twitter's crawler.
 *
 * Resolved rather than hardcoded, in this order:
 *
 * 1. NEXT_PUBLIC_SITE_URL, once a real domain is attached. Set it and nothing
 *    else in here needs editing.
 * 2. The Vercel deployment URL, so preview builds describe themselves instead
 *    of pointing every card and canonical at production.
 * 3. Local development.
 */
const FALLBACK = "http://localhost:3001";

function resolve(): string {
  const explicit = process.env.NEXT_PUBLIC_SITE_URL;
  if (explicit) return explicit.replace(/\/+$/, "");

  // Vercel sets this without a scheme.
  const vercel = process.env.VERCEL_PROJECT_PRODUCTION_URL ?? process.env.VERCEL_URL;
  if (vercel) return `https://${vercel}`;

  return FALLBACK;
}

export const SITE_URL = resolve();

/** Every route worth pointing a crawler at. Gated and error pages are not. */
export const PUBLIC_ROUTES = ["/", "/guide", "/wall", "/experiences", "/join"] as const;
