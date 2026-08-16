import "server-only";

import type { Session } from "next-auth";

import { auth } from "@/auth";
import { signupForGoogleSub, type SignupRow } from "@/lib/db";

/**
 * Who is looking at the page, in the two parts the site actually cares about.
 *
 * They are genuinely separate states and the UI has to tell them apart:
 *
 * * signed out - nothing but a "continue with Google" button;
 * * signed in, no profile - Google knows them, the wall does not, so they get
 *   the onboarding form rather than a post button;
 * * signed in with a profile - on the wall, and allowed to post.
 *
 * Returning an unreachable database as "no profile" rather than throwing keeps
 * the pages readable when Neon is cold or down, the same way the wall itself
 * degrades to an empty list.
 */
export type Viewer = {
  signedIn: boolean;
  /** Their name on the Google account, used to prefill the profile form. */
  googleName: string | null;
  /** Their row on the wall, once they have finished a profile. */
  signup: SignupRow | null;
};

const SIGNED_OUT: Viewer = {
  signedIn: false,
  googleName: null,
  signup: null,
};

export async function viewer(): Promise<Viewer> {
  // `Session | null`, not `Awaited<ReturnType<typeof auth>>`: the `auth` export
  // is overloaded and also serves as middleware, so inferring from it picks up
  // the middleware signature instead of the session one.
  let session: Session | null = null;
  try {
    session = await auth();
  } catch (error) {
    // Missing AUTH_SECRET or a malformed cookie. Every page here reads fine
    // signed out, and the whole site becoming a 500 because sign-in is
    // misconfigured would be a much worse failure than a hidden post button.
    console.error("session unavailable", error);
    return SIGNED_OUT;
  }

  const sub = session?.user?.id;
  if (!sub) return SIGNED_OUT;

  const googleName = session?.user?.name ?? null;
  try {
    return { signedIn: true, googleName, signup: await signupForGoogleSub(sub) };
  } catch (error) {
    console.error("profile lookup failed", error);
    return { signedIn: true, googleName, signup: null };
  }
}
