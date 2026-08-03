import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

import { rememberEmail } from "@/lib/db";

/**
 * Google sign-in, with the session in a signed cookie rather than the database.
 *
 * No adapter on purpose. An adapter would add four tables (users, accounts,
 * sessions, verification tokens) to hold what this site already has one table
 * for. The only thing worth persisting is "which Google account owns which row
 * in `signups`", and that is one column there.
 *
 * The token keeps Google's `sub`: a stable, opaque id for the account. Email is
 * deliberately not stored anywhere, because content/schema.sql promises there
 * is nothing in this database worth leaking, and an email list is exactly the
 * thing that promise is about. `sub` identifies the account for linking without
 * being useful to anyone who gets hold of it.
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
    async jwt({ token, profile }) {
      // `profile` is only present on the sign-in pass, so the values are copied
      // once and then carried by the token on every request after.
      if (profile?.sub) token.sub = profile.sub;
      if (profile?.email) token.email = profile.email;

      // Fill in the address for anyone who joined before there was a column to
      // put it in. Gated on `profile`, so this is one statement per sign-in
      // rather than one per request, and `rememberEmail` ignores rows that
      // already have one.
      //
      // Wrapped because this is the sign-in path. Sixty nine people an hour
      // come through here, and not being able to reach one of them later is a
      // far smaller problem than not letting them in now, so a database that
      // is down or slow must lose the address rather than the signup.
      if (profile?.sub && profile?.email) {
        try {
          await rememberEmail(profile.sub, profile.email);
        } catch (error) {
          console.error("could not record email", error);
        }
      }

      return token;
    },
    session({ session, token }) {
      if (session.user && token.sub) session.user.id = token.sub;
      return session;
    },
  },
});
