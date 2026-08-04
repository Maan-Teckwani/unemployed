import "server-only";

import { Avatar, Style } from "@dicebear/core";

import { GENDER_OPTIONS, type Gender } from "./gender-options.ts";

/**
 * SERVER ONLY. Importing this from a client component ships the Open Peeps
 * style definition, several hundred KB of JSON, to every visitor. The
 * `server-only` import above turns that mistake into a build error instead of a
 * silent regression, which is the whole reason it is the first line.
 *
 * Nothing in the browser ever renders an avatar. Every avatar on the site and
 * in the local app is an `<img>` pointing at /api/avatar, which calls this. One
 * consequence worth knowing: a wall of two hundred avatars is two hundred
 * cached image requests and zero JavaScript.
 */

// The style JSON is loaded once per server process, on the first avatar
// requested rather than at import time, so a cold start that never renders an
// avatar never pays for it.
let stylePromise: Promise<Style> | null = null;

function getStyle(): Promise<Style> {
  stylePromise ??= import("@dicebear/styles/open-peeps.json", {
    with: { type: "json" },
  }).then((module) => new Style(module.default));
  return stylePromise;
}

// Rendering is deterministic, so the same request can be answered from memory.
// Bounded because a lambda has little of it and the wall is unbounded.
const cache = new Map<string, string>();
const CACHE_LIMIT = 500;

export async function renderAvatar(seed: string, gender: Gender): Promise<string> {
  const key = `${gender}:${seed}`;
  const cached = cache.get(key);
  if (cached) {
    // Re-insert so a hit counts as recent use. A Map iterates in insertion
    // order, which is the whole mechanism the eviction below relies on.
    cache.delete(key);
    cache.set(key, cached);
    return cached;
  }

  const style = await getStyle();
  const svg = new Avatar(style, { seed, ...GENDER_OPTIONS[gender] }).toString();

  // Drop the least recently used one, not all five hundred. Emptying the whole
  // cache on every overflow meant the join page, which now asks for a dozen
  // fresh faces at a time, could evict the wall the reader is about to scroll.
  if (cache.size >= CACHE_LIMIT) {
    const oldest = cache.keys().next().value;
    if (oldest !== undefined) cache.delete(oldest);
  }
  cache.set(key, svg);
  return svg;
}

/** Seeds come from the URL, so they are checked before they reach the renderer. */
export function isValidSeed(seed: string): boolean {
  return /^[a-z0-9-]{1,64}$/i.test(seed);
}
