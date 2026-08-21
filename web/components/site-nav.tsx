"use client";

import Link from "next/link";
import { Logo } from "@/components/logo";
import { NavLink } from "@/components/nav/nav-link";
import { SetupMenu } from "@/components/nav/setup-menu";
import { StackPip } from "@/components/stack/stack-pip";
import { useStack } from "@/components/stack/stack-provider";
import { ThemeToggle } from "@/components/theme-toggle";

/**
 * Two tiers, because nine equal links were not a navigation.
 *
 * The row holds the four places the daily loop actually goes. The four you
 * configure once — knowledge base, profile, templates, filters — moved behind
 * Setup, which is not hiding them: they were competing for attention with the
 * two pages you open every morning, and losing to them anyway.
 */
const PRIMARY = [
  { href: "/today", label: "Apply today" },
  { href: "/jobs", label: "Jobs" },
  { href: "/roadmap", label: "Skills & Roadmap" },
  { href: "/manual-jd", label: "Paste JD" },
  { href: "/board", label: "Board" },
];


export function SiteNav() {
  const { counts, setupIncomplete } = useStack();

  return (
    <header
      className="sticky top-0 z-50 border-b bg-surface-raised/85 backdrop-blur-md"
      // Held still across page transitions. It is the same header before and
      // after, so cross-fading it makes the one fixed thing on screen flicker.
      style={{ viewTransitionName: "site-header" }}
    >
      <nav className="mx-auto flex min-h-14 max-w-5xl flex-wrap items-center gap-x-6 gap-y-2 px-6 py-2">
        <Link
          href="/"
          className="rounded-sm focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
        >
          <Logo />
        </Link>

        <div className="flex flex-wrap items-center gap-x-5 gap-y-1">
          {PRIMARY.map((l) => (
            <NavLink
              key={l.href}
              href={l.href}
              label={l.label}
              // The count answers "is there work?" without a click, and it is
              // re-read after every navigation because applying changes it.
              badge={l.href === "/today" ? counts?.rankable : undefined}
            />
          ))}
          <SetupMenu incomplete={setupIncomplete} />
        </div>

        <div className="ml-auto flex items-center gap-1">
          <StackPip />
          <ThemeToggle />
        </div>
      </nav>
    </header>
  );
}
