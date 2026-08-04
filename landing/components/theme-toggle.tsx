"use client";

import { useSyncExternalStore } from "react";

import { copy } from "@/lib/copy";

/**
 * Light and dark, chosen by the reader.
 *
 * The class on <html> is the source of truth, not a copy of it held in state.
 * The blocking script in the layout has already set that class before React
 * runs, so anything this component remembered separately would start out as a
 * guess, and a guess is what shows the wrong icon for the first frame.
 *
 * So it subscribes to the element instead. Toggling writes the class and the
 * observer reports it back, which means the button is correct even if something
 * else changes the theme.
 *
 * The server cannot know which theme was picked, so its snapshot is null and
 * the button renders empty. useSyncExternalStore is the hook that makes that
 * safe: it re-reads on the client after hydration by design, rather than being
 * a mismatch to warn about.
 */
function subscribe(onChange: () => void): () => void {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class"],
  });
  return () => observer.disconnect();
}

export function ThemeToggle() {
  const dark = useSyncExternalStore(
    subscribe,
    () => document.documentElement.classList.contains("dark"),
    () => null,
  );

  function toggle() {
    const next = !dark;
    document.documentElement.classList.toggle("dark", next);
    // Writing the choice is what makes it survive a reload, and what tells the
    // blocking script to stop following the operating system for this reader.
    try {
      localStorage.setItem("theme", next ? "dark" : "light");
    } catch {
      // Private mode with storage denied. The toggle still works for this page.
    }
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={dark ? copy.nav.theme.toLight : copy.nav.theme.toDark}
      className="text-muted-foreground hover:text-foreground grid size-8 shrink-0 place-items-center rounded-md transition-colors focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      {dark === null ? null : dark ? <SunIcon /> : <MoonIcon />}
    </button>
  );
}

/* Drawn inline rather than pulled from an icon package: two shapes do not
   justify a dependency, and these inherit currentColor for free. */

function MoonIcon() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="size-4"
    >
      <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z" />
    </svg>
  );
}

function SunIcon() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="size-4"
    >
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  );
}
