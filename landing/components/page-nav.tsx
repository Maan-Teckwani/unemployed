"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Logo } from "./logo";
import { scrollToTop } from "./smooth-scroll";
import { ThemeToggle } from "./theme-toggle";
import { copy } from "@/lib/copy";

/**
 * Sticky section nav.
 *
 * Transparent over the hero and only growing a border and a backdrop once you
 * scroll past it, so it does not put a line through the middle of the opening
 * screen. The section links are plain anchors, which means back and forward
 * work and a link to a section is shareable.
 *
 * The links collapse into a menu below lg rather than below sm. Five labels,
 * a wordmark, a theme button and a call to action do not fit a 14 unit bar at
 * tablet width, and the old rule simply hid the links with nothing in their
 * place, so setup was unreachable on a phone.
 */
export function PageNav({ signedIn = false }: { signedIn?: boolean }) {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Escape closes it, because a panel covering the page with no visible way out
  // is the one thing a keyboard reader cannot recover from.
  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 transition-colors duration-300 ${
        scrolled || menuOpen
          ? "border-b bg-background/85 backdrop-blur-md"
          : "border-b border-transparent"
      }`}
    >
      {/* Tighter below sm than it used to be, and that is what pays for the
          contribute tag. The bar was carrying a wordmark, a theme button, a
          call to action and a menu button with about thirteen pixels to spare
          at 375, so adding anything at all pushed the menu button off the right
          edge, and the menu is the only way to the links on a phone. */}
      <nav className="mx-auto flex h-14 w-full max-w-5xl items-center gap-2 px-4 sm:gap-6 sm:px-6">
        {/* Home, not "#top". The nav is on /wall and /experiences too, where an
            anchor just scrolls the page you are already on and leaves you with
            no way back to the landing page. */}
        <Link
          href="/"
          onClick={(e) => {
            if (pathname === "/") {
              e.preventDefault();
              // Through Lenis when it is running, or the browser when it is
              // not. Calling window.scrollTo directly here would be overwritten
              // by Lenis on its very next frame.
              scrollToTop();
            }
          }}
          className="shrink-0 rounded-sm focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          <Logo />
        </Link>

        <div className="text-muted-foreground ml-auto hidden items-center gap-6 text-sm lg:flex">
          {copy.nav.links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="hover:text-foreground rounded-sm whitespace-nowrap transition-colors focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
            >
              {link.label}
            </a>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-1 sm:gap-2 lg:ml-0 lg:gap-3">
          {/* A tag rather than a sixth label, and a tag rather than a bare cup.
              The row of links already does not fit a tablet, which is why it
              collapses at lg, so this cannot go in it. But an unlabelled icon
              beside another unlabelled icon is furniture, and this is the one
              link on the page that has to be noticed, so it carries the word
              and the one colour that is not on the rest of the bar.

              The word is dropped on the narrowest screens and nowhere else.
              At 375 pixels the bar is already carrying a wordmark, a theme
              button, the main call to action and a menu button, and the first
              thing an overflow costs is the call to action. The collapsed menu
              spells it out in full. */}
          <Link
            href="/coffee"
            aria-label={copy.nav.coffee.aria}
            title={copy.nav.coffee.label}
            aria-current={pathname === "/coffee" ? "page" : undefined}
            className="nav-coffee"
          >
            <CupIcon />
            <span className="hidden sm:inline">{copy.nav.coffee.tag}</span>
          </Link>

          <ThemeToggle />

          <Link
            href={signedIn ? "/profile" : "/join"}
            className="border-foreground bg-foreground text-background rounded-lg border px-3 py-1.5 text-sm font-medium whitespace-nowrap transition-opacity hover:opacity-85 focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
          >
            {signedIn ? "Profile" : copy.nav.cta}
          </Link>

          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            aria-expanded={menuOpen}
            aria-controls="nav-menu"
            aria-label={menuOpen ? copy.nav.menu.close : copy.nav.menu.open}
            className="text-muted-foreground hover:text-foreground grid size-8 shrink-0 place-items-center rounded-md transition-colors focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none lg:hidden"
          >
            <MenuIcon open={menuOpen} />
          </button>
        </div>
      </nav>

      {/* Rendered only when open rather than hidden with a class: the links are
          real anchors, and a screen reader should not find a second copy of
          every one of them sitting off screen. */}
      {menuOpen && (
        <div id="nav-menu" className="border-t lg:hidden">
          <ul className="mx-auto flex w-full max-w-5xl flex-col px-4 py-2 sm:px-6">
            {copy.nav.links.map((link) => (
              <li key={link.href}>
                <a
                  href={link.href}
                  onClick={() => setMenuOpen(false)}
                  className="hover:text-foreground text-muted-foreground block rounded-sm py-2.5 text-sm transition-colors focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
                >
                  {link.label}
                </a>
              </li>
            ))}
            {/* The cup is a picture in the bar above and a sentence in here.
                An icon with no label is fine beside a theme toggle and is not
                fine as the only entry in a list of words. */}
            <li>
              <Link
                href="/coffee"
                onClick={() => setMenuOpen(false)}
                className="hover:text-foreground text-muted-foreground block rounded-sm py-2.5 text-sm transition-colors focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
              >
                {copy.nav.coffee.label}
              </Link>
            </li>
          </ul>
        </div>
      )}
    </header>
  );
}

/* A mug, at sixteen pixels. Everything that makes the one at /coffee a mug is
   gone at this size, so this is the two lines that survive: a tapered cup with
   a handle, and one curl of steam so it reads as full rather than as a bucket. */
function CupIcon() {
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
      <path d="M4 9h12v6a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4Z" />
      <path d="M16 11h1.5a2.5 2.5 0 0 1 0 5H16" />
      <path d="M9 2c-1 1.4.9 2 0 3.5M13 2c-1 1.4.9 2 0 3.5" />
    </svg>
  );
}

function MenuIcon({ open }: { open: boolean }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      className="size-4"
    >
      {open ? (
        <path d="M6 6l12 12M18 6L6 18" />
      ) : (
        <path d="M3 7h18M3 12h18M3 17h18" />
      )}
    </svg>
  );
}
