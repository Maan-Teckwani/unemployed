import type { Metadata } from "next";
import Link from "next/link";
import { headers } from "next/headers";

import { CoffeeForm } from "@/components/coffee/coffee-form";
import { PageNav } from "@/components/page-nav";
import { Reveal } from "@/components/reveal";
import { isConfigured } from "@/lib/coffee";
import { copy } from "@/lib/copy";
import { currencyForCountry } from "@/lib/currency";
import { viewer } from "@/lib/viewer";

export const metadata: Metadata = {
  title: copy.meta.pages.coffee,
  description: copy.meta.pages.coffeeDescription,
  alternates: { canonical: "/coffee" },
};

// The currency comes from a request header and the pay button depends on the
// session, so there is nothing here worth freezing at build time.
export const dynamic = "force-dynamic";

/**
 * The tip jar.
 *
 * Priced in the reader's own currency and charged in rupees, which the page
 * says out loud rather than letting somebody discover it on their statement.
 * See lib/currency.ts for why those are two different numbers.
 *
 * The country comes from the CDN's own geo header rather than from the browser.
 * Asking the browser means either a locale, which is what language somebody
 * reads and not where they are, or a timezone, which is a guess. Vercel already
 * knows, having just routed the request.
 *
 * The cup and the button are the whole page and they are above the fold, on one
 * screen, with nothing to scroll past first. That is the layout rule here and
 * it is why the argument for why any of this costs money lives underneath them
 * rather than in front of them: somebody who arrived meaning to press the
 * button should not have to read a paragraph to find it, and somebody who wants
 * the reasoning will scroll for it.
 */
export default async function CoffeePage() {
  const [me, requestHeaders] = await Promise.all([viewer(), headers()]);
  const currency = currencyForCountry(requestHeaders.get("x-vercel-ip-country"));

  return (
    <>
      <PageNav signedIn={me.signedIn} />
      <main id="top">
        {/* One screen on anything with the height for it. Centred rather than
            top aligned, so the cup sits in the middle of a tall window instead
            of hanging off the nav. Phones fall out of this and scroll, which is
            correct: a mug and a set of controls stacked do not fit a phone, and
            squeezing them until they do would cost the cup its size. */}
        <section className="flex flex-col justify-center px-6 pt-20 pb-12 md:min-h-[100svh] md:px-12 md:pb-14 lg:px-24">
          <div className="mx-auto w-full max-w-5xl">
            <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
              <h1 className="font-serif text-3xl leading-tight sm:text-4xl">
                {copy.coffee.heading}
              </h1>
              <p className="text-muted-foreground font-serif text-xl italic">
                {copy.coffee.tagline}
              </p>
            </div>

            <div className="card mt-6 p-4 sm:mt-8 sm:p-10">
              <CoffeeForm
                currency={currency}
                configured={isConfigured()}
                onWall={me.signup !== null}
                name={me.signup?.name ?? me.googleName}
              />
            </div>

            <p className="text-muted-foreground mt-4 max-w-2xl text-sm leading-relaxed sm:mt-5">
              {copy.coffee.kicker}
            </p>
          </div>
        </section>

        {/* The reasoning, underneath. Everything a reader might want before
            deciding is here, and nothing here is in the way of deciding. */}
        <section className="border-t px-6 py-24 md:px-12 lg:px-24">
          <div className="mx-auto w-full max-w-5xl">
            <Reveal className="max-w-2xl">
              <h2 className="text-muted-foreground font-mono text-[11px] tracking-[0.2em] uppercase">
                {copy.coffee.where.heading}
              </h2>
              <p className="mt-6 text-lg leading-relaxed">{copy.coffee.body}</p>
            </Reveal>

            <div className="mt-12 grid gap-6 md:grid-cols-3">
              {copy.coffee.where.items.map((item, i) => (
                <Reveal key={item.title} delay={i * 90}>
                  <article className="card h-full">
                    <h3 className="font-serif text-xl leading-tight">{item.title}</h3>
                    <p className="text-muted-foreground mt-3 text-sm leading-relaxed">
                      {item.body}
                    </p>
                  </article>
                </Reveal>
              ))}
            </div>

            <p className="text-muted-foreground mt-10 text-sm">
              <Link href="/legal" className="hover:text-foreground underline underline-offset-4">
                {copy.footer.legal}
              </Link>
            </p>
          </div>
        </section>
      </main>
    </>
  );
}
