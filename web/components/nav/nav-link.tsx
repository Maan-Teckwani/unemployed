"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/**
 * One primary destination.
 *
 * The active state is an underline drawn under the label rather than a colour
 * change, because in a greyscale app "slightly darker grey" is not a signal
 * anyone reads. `aria-current` carries the same fact for screen readers.
 */
export function NavLink({
  href,
  label,
  badge,
}: {
  href: string;
  label: string;
  /** A count worth seeing before you click, e.g. how many roles are waiting. */
  badge?: number | null;
}) {
  const pathname = usePathname();
  const active = pathname === href;

  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={`relative rounded-sm py-1 text-sm transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 ${
        active ? "text-foreground font-medium" : "text-muted-foreground"
      }`}
    >
      {label}
      {badge != null && badge > 0 && (
        <span className="data ml-1 text-data-sm text-muted-foreground">{badge}</span>
      )}
      {active && (
        <span
          className="absolute -bottom-px left-0 right-0 h-px bg-foreground"
          aria-hidden
        />
      )}
    </Link>
  );
}
