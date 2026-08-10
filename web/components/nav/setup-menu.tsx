"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Check, ChevronDown } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

/**
 * The four pages you set up once and then rarely open again.
 *
 * They used to sit in the same row as the daily loop, which made nine
 * equal-looking links and buried the two that matter every morning. Grouping
 * them is not hiding them: the trigger shows a dot while any of them is still
 * unconfigured, and the current one is ticked when you are on it.
 */
const SETUP = [
  { href: "/kb", label: "Knowledge Base", hint: "What you have actually done" },
  { href: "/profile", label: "Profile", hint: "The header of every resume" },
  { href: "/templates", label: "Templates", hint: "Your own LaTeX resume" },
  { href: "/settings", label: "Filters", hint: "What you will apply to" },
];

export function SetupMenu({ incomplete = false }: { incomplete?: boolean }) {
  const pathname = usePathname();
  const here = SETUP.some((s) => pathname === s.href);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={`relative flex items-center gap-1 rounded-sm py-1 text-sm transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 ${
          here ? "text-foreground font-medium" : "text-muted-foreground"
        }`}
      >
        Setup
        <ChevronDown className="size-3.5" aria-hidden />
        {incomplete && (
          <span
            className="size-1.5 rounded-full bg-foreground"
            aria-label="Setup is not finished"
          />
        )}
        {here && (
          <span
            className="absolute -bottom-px left-0 right-4 h-px bg-foreground"
            aria-hidden
          />
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        {SETUP.map((s) => (
          <DropdownMenuItem
            key={s.href}
            render={<Link href={s.href} />}
            className="flex-col items-start gap-0.5"
          >
            <span className="flex w-full items-center justify-between gap-2">
              {s.label}
              {pathname === s.href && <Check className="size-3.5" aria-hidden />}
            </span>
            <span className="text-xs text-muted-foreground">{s.hint}</span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
