import type { MetadataRoute } from "next";

import { PUBLIC_ROUTES, SITE_URL } from "@/lib/site";

/**
 * The five pages worth indexing.
 *
 * /profile is signed in only and /auth-error exists to be landed on, not found,
 * so neither belongs here. The list lives in lib/site.ts because robots.ts needs
 * the same idea of what is public.
 *
 * Every page is force-dynamic, so there are no build times to report. The wall
 * and the snippets change whenever somebody joins or writes one, which is what
 * `changeFrequency` is for.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  return PUBLIC_ROUTES.map((route) => ({
    url: `${SITE_URL}${route}`,
    lastModified: now,
    changeFrequency: route === "/" || route === "/guide" ? "monthly" : "daily",
    priority: route === "/" ? 1 : 0.7,
  }));
}
