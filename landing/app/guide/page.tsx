import type { Metadata } from "next";

import { PageNav } from "@/components/page-nav";
import { viewer } from "@/lib/viewer";
import { InstallSection } from "@/components/install-section";
import { copy } from "@/lib/copy";

export const metadata: Metadata = {
  title: "How to use unemployed",
  description:
    "Half an hour of setup, then ten minutes a day. What to write down before you start, and the four ways to get a bad result.",
  alternates: { canonical: "/guide" },
};

/**
 * The guide.
 *
 * Static, and deliberately not gated behind joining the wall: someone deciding
 * whether this is worth installing should be able to read what using it
 * actually involves. The install commands are the thing worth trading a name
 * for, not the advice.
 */
export default async function GuidePage() {
  const { guide } = copy;
  const me = await viewer();

  return (
    <>
      <PageNav signedIn={me.signedIn} />
      <main id="top" className="px-6 pt-28 pb-32 md:px-12 lg:px-24">
        <div className="mx-auto w-full max-w-3xl">
          <p className="text-muted-foreground font-mono text-[11px] tracking-[0.2em] uppercase">
            {guide.label}
          </p>
          <h1 className="mt-5 font-serif text-4xl leading-[1.1] text-balance sm:text-5xl">
            {guide.heading}
          </h1>
          <p className="text-muted-foreground mt-6 text-lg leading-relaxed">{guide.intro}</p>

          <Phase phase={guide.firstRun} numbered />
          <Phase phase={guide.daily} numbered />
          <Phase phase={guide.weekly} />

          <section className="mt-20">
            <Label>{guide.mistakes.label}</Label>
            <h2 className="mt-4 font-serif text-3xl leading-tight">{guide.mistakes.heading}</h2>
            <ul className="mt-8 grid gap-4 sm:grid-cols-2">
              {guide.mistakes.items.map((item) => (
                <li key={item.title} className="card">
                  <h3 className="font-serif text-xl leading-tight">{item.title}</h3>
                  <p className="text-muted-foreground mt-2 text-sm leading-relaxed">{item.body}</p>
                </li>
              ))}
            </ul>
          </section>

          <section className="mt-20 border-t pt-10">
            <h2 className="font-serif text-2xl leading-tight">{guide.closing.heading}</h2>
            <p className="text-muted-foreground mt-3 text-base leading-relaxed">
              {guide.closing.body}
            </p>
          </section>
        </div>
      </main>
      <InstallSection />
    </>
  );
}

// `copy` is `as const`, so everything in it arrives readonly. Not every step
// has a duration or a note, which is what the optional fields are for.
type Step = {
  readonly title: string;
  readonly body: string;
  readonly time?: string;
  readonly why?: string;
};

function Phase({
  phase,
  numbered = false,
}: {
  phase: { readonly label: string; readonly heading: string; readonly steps: readonly Step[] };
  numbered?: boolean;
}) {
  return (
    <section className="mt-20">
      <Label>{phase.label}</Label>
      <h2 className="mt-4 font-serif text-3xl leading-tight">{phase.heading}</h2>

      <ol className="mt-8 space-y-8">
        {phase.steps.map((step, i) => (
          <li key={step.title} className="border-l pl-6">
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              {numbered && (
                <span className="text-muted-foreground/60 font-mono text-xs tabular-nums">
                  {String(i + 1).padStart(2, "0")}
                </span>
              )}
              <h3 className="font-serif text-xl leading-tight">{step.title}</h3>
              {step.time && (
                <span className="text-muted-foreground rounded-full border px-2.5 py-0.5 font-mono text-[11px] whitespace-nowrap">
                  {step.time}
                </span>
              )}
            </div>
            <p className="mt-3 text-base leading-relaxed">{step.body}</p>
            {step.why && (
              <p className="text-muted-foreground bg-muted/40 mt-3 rounded-md px-4 py-3 text-sm leading-relaxed">
                {step.why}
              </p>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-muted-foreground font-mono text-[11px] tracking-[0.2em] uppercase">
      {children}
    </p>
  );
}
