import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

import { saveEmail } from "@/lib/db";

/**
 * Google sign-in, with the session in a signed cookie rather than the database.
 *
 * No adapter on purpose. An adapter would add four tables (users, accounts,
 * sessions, verification tokens) to hold what this site already has one table
 * for. The only thing worth persisting is "which Google account owns which row
 * in `signups`", and that is one column there.
 *
 * The token keeps Google's `sub` (a stable, opaque id for the account) and the
 * email address, and the sign-in pass writes that address into `signups.email`.
 * There is no question attached to it: the button people press sits directly
 * under copy that says the address is kept, never shown on the wall and never
 * given to anyone else, so pressing it is the agreement. See lib/copy.ts.
 */

/**
 * Bump this to sign everyone out.
 *
 * Sessions here are self contained cookies, so there is no table of them to
 * delete. A token that does not carry the current epoch is refused below and
 * its cookie cleared, which is the same effect as rotating AUTH_SECRET without
 * needing the hosting dashboard: deploying is what signs people out.
 *
 * It went to 2 when the address started being taken at sign-in, so that the
 * people already holding a cookie come back through Google once and get their
 * address recorded rather than waiting for their session to expire.
 */
const SESSION_EPOCH = 2;

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [Google],
  session: { strategy: "jwt" },
  // Only the failure destination is overridden. The sign in flow itself is
  // untouched, because it works: it takes about seventy people an hour and the
  // handful it loses are losing a cookie, not hitting a misconfigured server.
  // See app/auth-error/page.tsx.
  pages: { error: "/auth-error" },
  callbacks: {
    async jwt({ token, profile }) {
      // `profile` is only present on the sign-in pass, so this runs once per
      // sign-in and the values are then carried by the token on every request
      // after.
      if (profile?.sub) {
        token.sub = profile.sub;
        token.email = profile.email;
        token.epoch = SESSION_EPOCH;

        if (profile.email) {
          // The row may not exist yet, in which case this updates nothing and
          // the insert in app/api/signups does the writing instead.
          //
          // Caught rather than thrown: a cold or unreachable Neon must not turn
          // into a failed sign-in. The address is taken again on the next
          // sign-in, and losing it is a smaller failure than locking people out
          // of the site to protect a mailing list.
          try {
            await saveEmail(profile.sub, profile.email);
          } catch (error) {
            console.error("email save failed", error);
          }
        }

        return token;
      }

      // Every request after the sign-in pass. Returning null here clears the
      // session cookie, which is what makes the epoch above a sign-out switch.
      if (token.epoch !== SESSION_EPOCH) return null;

      return token;
    },
    session({ session, token }) {
      if (session.user && token.sub) session.user.id = token.sub;
      return session;
    },
  },
});
