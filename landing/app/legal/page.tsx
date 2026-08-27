import type { Metadata } from "next";
import Link from "next/link";

import { PageNav } from "@/components/page-nav";
import { copy } from "@/lib/copy";
import { viewer } from "@/lib/viewer";

export const metadata: Metadata = {
  title: copy.meta.pages.legal,
  description: copy.meta.pages.legalDescription,
  alternates: { canonical: "/legal" },
};

export const dynamic = "force-dynamic";

/**
 * Terms, refunds, privacy and a contact, on one page.
 *
 * One page rather than the usual four, because splitting six short sections
 * across four routes would be pretending there is more here than there is.
 * Somebody looking for the refund policy finds it by scrolling rather than by
 * guessing which of four links it is behind.
 *
 * It exists for two audiences. Anyone about to buy a coffee who wants to know
 * what happens if they change their mind, and Razorpay, whose review of a new
 * website checks that these things are written down and that the contact on
 * them is real.
 */
export default async function LegalPage() {
  const me = await viewer();

  return (
    <>
      <PageNav signedIn={me.signedIn} />
      <main id="top">
        <section className="px-6 pt-32 pb-24 md:px-12 lg:px-24">
          <div className="mx-auto w-full max-w-2xl">
            <h1 className="font-serif text-3xl leading-tight sm:text-4xl">
              {copy.legal.heading}
            </h1>
            <p className="text-muted-foreground mt-3 font-mono text-xs">{copy.legal.updated}</p>

            <div className="mt-14 space-y-12">
              {copy.legal.sections.map((section) => (
                <section key={section.title}>
                  <h2 className="font-serif text-xl leading-tight">{section.title}</h2>
                  <div className="mt-4 space-y-4">
                    {section.body.map((paragraph) => (
                      <p key={paragraph} className="text-muted-foreground leading-relaxed">
                        {paragraph}
                      </p>
                    ))}
                  </div>
                </section>
              ))}
            </div>

            {/* The address itself, once, at the end. Written as a mailto so it
                is one tap on a phone, and spelled out as text so it is still
                usable to anyone whose browser will not open a mail client. */}
            <p className="mt-12 border-t pt-8">
              <a
                href={`mailto:${copy.legal.email}`}
                className="font-medium underline underline-offset-4"
              >
                {copy.legal.email}
              </a>
            </p>

            <Link href="/" className="btn-outline mt-12 inline-flex">
              {copy.legal.backCta}
            </Link>
          </div>
        </section>
      </main>
    </>
  );
}
