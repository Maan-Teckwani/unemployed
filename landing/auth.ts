import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

/**
 * Google sign-in, with the session in a signed cookie rather than the database.
 *
 * No adapter on purpose. An adapter would add four tables (users, accounts,
 * sessions, verification tokens) to hold what this site already has one table
 * for. The only thing worth persisting is "which Google account owns which row
 * in `signups`", and that is one column there.
 *
 * The token keeps Google's `sub` (a stable, opaque id for the account) and the
 * email address. The address is stored in `signups.email`, but not from here.
 * This file used to write it in the `jwt` callback, which meant it was taken
 * from returning users on the way past: /join redirects anyone who already has
 * a row straight to the install steps, so the people whose address was being
 * recorded were exactly the people who never saw the sentence saying so.
 *
 * So the write moved to /join, where it is a thing someone agrees to rather
 * than a side effect of arriving. See app/join/page.tsx and lib/db.ts.
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

      // Nothing is written to the database here. The address rides the token
      // so /join can offer it, and goes no further until someone says yes.
      return token;
    },
    session({ session, token }) {
      if (session.user && token.sub) session.user.id = token.sub;
      return session;
    },
  },
});
