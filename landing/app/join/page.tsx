import type { Metadata } from "next";
import { redirect } from "next/navigation";

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
 * It renders whichever of the three states the viewer is in, rather than being
 * three routes, because they are steps in one flow and a signed-in user with no
 * profile has nowhere else sensible to be.
 */
export default async function JoinPage() {
  const { signedIn, googleName, signup } = await viewer();

  // Already done. Nothing to fill in, so go and look at the install steps.
  if (signup) redirect("/#install");

  return (
    <>
      <PageNav signedIn={signedIn} />
      <main id="top" className="px-6 pt-28 pb-32 md:px-12 lg:px-24">
        <div className="mx-auto w-full max-w-3xl">
          <p className="text-muted-foreground font-mono text-[11px] tracking-[0.2em] uppercase">
            {copy.join.label}
          </p>
          <h1 className="mt-5 font-serif text-3xl leading-tight sm:text-4xl">
            {signedIn ? copy.auth.profileHeading : copy.auth.signInHeading}
          </h1>
          <p className="text-muted-foreground mt-4 text-base leading-relaxed">
            {signedIn ? copy.auth.profileBody : copy.auth.signInBody}
          </p>

          <div className="mt-8">
            {signedIn ? (
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
