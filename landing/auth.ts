import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

import { saveEmail } from "@/lib/db";
import { identify, isCurrentEpoch, SESSION_EPOCH } from "@/lib/session";

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
 *
 * SESSION_EPOCH, in lib/session.ts, is how everyone gets signed out.
 */
export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [Google],
  session: { strategy: "jwt" },
  // Only the failure destination is overridden. The sign in flow itself is
  // untouched, because it works: it takes about seventy people an hour and the
  // handful it loses are losing a cookie, not hitting a misconfigured server.
  // See app/auth-error/page.tsx.
  pages: { error: "/auth-error" },
  callbacks: {
    async jwt({ token, account, profile, user }) {
      // `account` is what says this is the sign-in pass, rather than `profile`
      // or `profile.sub`. Both of those are the provider's response and can in
      // principle come back thin; `account` is next-auth's own record of the
      // sign-in and is always there. Getting this wrong is expensive in one
      // direction: a sign-in mistaken for an ordinary request falls through to
      // the epoch check below, returns null, and the person cannot sign in at
      // all. So the test is the one that cannot be empty.
      if (account) {
        const { sub, email } = identify(profile, user, token);

        if (sub) token.sub = sub;
        if (email) token.email = email;
        // Stamped on the way in, so a sign-in is never refused by the check
        // below no matter what the provider sent.
        token.epoch = SESSION_EPOCH;

        if (sub && email) {
          // The row may not exist yet, in which case this updates nothing and
          // the insert in app/api/signups does the writing instead.
          //
          // Caught rather than thrown: a cold or unreachable Neon must not turn
          // into a failed sign-in. The address is taken again on the next
          // sign-in, and losing it is a smaller failure than locking people out
          // of the site to protect a mailing list.
          try {
            await saveEmail(sub, email);
          } catch (error) {
            console.error("email save failed", error);
          }
        }

        return token;
      }

      // Every request after the sign-in pass. Returning null here clears the
      // session cookie, which is what makes the epoch a sign-out switch.
      if (!isCurrentEpoch(token)) return null;

      return token;
    },
    session({ session, token }) {
      if (session.user && token.sub) session.user.id = token.sub;
      return session;
    },
  },
});
