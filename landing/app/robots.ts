import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/site";

/**
 * Crawl the pages, skip the plumbing.
 *
 * /api returns JSON that duplicates what the pages already say, /profile is
 * signed in only, and /auth-error is a dead end reached by redirect. None of
 * them help anybody arriving from a search.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/api/", "/profile", "/auth-error"],
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
