import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { EmailConsent } from "@/components/email-consent";
import { PageNav } from "@/components/page-nav";
import { ProfileForm } from "@/components/profile-form";
import { SignInButton, SignOutButton } from "@/components/sign-in-button";
import { copy } from "@/lib/copy";
import { viewer } from "@/lib/viewer";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: copy.meta.pages.join,
  description: copy.meta.pages.joinDescription,
  alternates: { canonical: "/join" },
};

/**
 * The one page that turns a visitor into someone on the wall.
 *
 * It renders whichever of the four states the viewer is in, rather than being
 * four routes, because they are steps in one flow and a signed-in user with no
 * profile has nowhere else sensible to be.
 *
 * The fourth state is the odd one: already on the wall, but never asked about
 * their email, because they joined before there was a column for it. They used
 * to be redirected straight past this page, which is precisely why they never
 * read the sentence saying the address is now kept. So they get stopped here
 * once, and then never again whichever way they answer.
 */
export default async function JoinPage() {
  const { signedIn, googleName, signup, needsEmailConsent } = await viewer();

  // Already done, and already asked. Go and look at the install steps.
  if (signup && !needsEmailConsent) redirect("/#install");

  const asking = Boolean(signup && needsEmailConsent);

  return (
    <>
      <PageNav signedIn={signedIn} />
      <main id="top" className="px-6 pt-28 pb-32 md:px-12 lg:px-24">
        <div className="mx-auto w-full max-w-3xl">
          <p className="text-muted-foreground font-mono text-[11px] tracking-[0.2em] uppercase">
            {copy.join.label}
          </p>
          <h1 className="mt-5 font-serif text-3xl leading-tight sm:text-4xl">
            {asking
              ? copy.auth.consentHeading
              : signedIn
                ? copy.auth.profileHeading
                : copy.auth.signInHeading}
          </h1>
          <p className="text-muted-foreground mt-4 text-base leading-relaxed">
            {asking
              ? copy.auth.consentBody
              : signedIn
                ? copy.auth.profileBody
                : copy.auth.signInBody}
          </p>

          <div className="mt-8">
            {asking ? (
              <EmailConsent />
            ) : signedIn ? (
              <ProfileForm
                defaultName={googleName ?? ""}
                initialSeed={crypto.randomUUID().slice(0, 8)}
              />
            ) : (
              <SignInButton />
            )}
          </div>

          <p className="text-muted-foreground mt-6 text-xs">
            {signedIn ? copy.auth.notYou : copy.auth.whyGoogle}{" "}
            {signedIn && <SignOutButton />}
          </p>
        </div>
      </main>
    </>
  );
}
