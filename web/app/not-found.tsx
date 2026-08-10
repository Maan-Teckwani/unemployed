import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";

/**
 * Next's built-in 404 is one line of text on a white page.
 *
 * That is a dead end here, because the interesting case is not "you typed the
 * address wrong" — it is a page that plainly exists in the source and 404s
 * anyway. That happens when the dev server is serving a `.next` cache left
 * behind by a previous run that was killed rather than stopped, which is what
 * closing the window does. Naming it turns a mystery into one command.
 */

const PAGES = [
  { href: "/", label: "Home" },
  { href: "/today", label: "Apply today" },
  { href: "/jobs", label: "Jobs" },
  { href: "/kb", label: "Knowledge Base" },
  { href: "/settings", label: "Filters" },
];

export default function NotFound() {
  return (
    <div className="max-w-prose space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">There is no page at this address</h1>
        <p className="text-muted-foreground mt-2 text-sm">
          If you got here from a link inside the app rather than by typing the
          address, the page does exist and this copy of the app has not been
          built with it. That is almost always a stale build: stop the app,
          delete <code className="bg-muted rounded px-1">web/.next</code>, and
          start it again.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {PAGES.map((p) => (
          <Link
            key={p.href}
            href={p.href}
            className={buttonVariants({ variant: "outline", size: "sm" })}
          >
            {p.label}
          </Link>
        ))}
      </div>
    </div>
  );
}
