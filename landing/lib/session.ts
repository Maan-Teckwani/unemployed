/**
 * What a session cookie carries, and who a sign-in turned out to be.
 *
 * Split out of auth.ts so it can be tested. auth.ts imports next-auth and the
 * database, and neither survives being loaded by `node --test`, so anything
 * left in there can only be checked by reading it as text. The two decisions
 * that matter on a sign-in are here instead, as functions over plain objects.
 */

/**
 * Bump this to sign everyone out.
 *
 * Sessions here are self contained cookies, so there is no table of them to
 * delete. A token that does not carry the current epoch is refused and its
 * cookie cleared, which is the same effect as rotating AUTH_SECRET without
 * needing the hosting dashboard: deploying is what signs people out.
 *
 * It went to 2 when the address started being taken at sign-in, so that the
 * people already holding a cookie come back through Google once and get their
 * address recorded rather than waiting for their session to expire.
 */
export const SESSION_EPOCH = 2;

/** The three shapes a sign-in offers an id and an address in. */
type Claims = { sub?: string | null; email?: string | null; id?: string | null };

export type Identity = { sub: string | null; email: string | null };

/**
 * Who just signed in, from whichever of the three the provider filled in.
 *
 * Google normally puts both on `profile`, and everything here is built on that
 * being true. It is not worth betting a launch on: next-auth also derives a
 * `user` from the same response, and a returning token already holds both from
 * last time. Taking the first non-empty of the three costs nothing and means an
 * unusual response degrades to a missing address rather than to a missing
 * account, which is what would happen if `sub` came back empty and the caller
 * treated that as "not a sign-in".
 *
 * Empty strings are treated as absent. A blank `sub` would otherwise become a
 * row owner that no later sign-in can match.
 */
export function identify(...sources: (Claims | null | undefined)[]): Identity {
  const first = (pick: (c: Claims) => string | null | undefined) => {
    for (const source of sources) {
      const value = source ? pick(source) : null;
      if (typeof value === "string" && value.trim() !== "") return value;
    }
    return null;
  };
  return {
    sub: first((c) => c.sub ?? c.id),
    email: first((c) => c.email),
  };
}

/**
 * Whether a token from a previous deploy is still allowed to be a session.
 *
 * Checked only on requests that are not a sign-in. A sign-in stamps the current
 * epoch itself, so this can never be the thing that stops someone getting in.
 */
export function isCurrentEpoch(token: Record<string, unknown>): boolean {
  return token.epoch === SESSION_EPOCH;
}
