import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import test from "node:test";

/**
 * The email column is written and never read back.
 *
 * `SignupRow` is handed to client components, so every field on it is
 * serialised into the HTML that goes to whoever is looking at the page. A
 * `select email` added to any of the read paths would put addresses there, and
 * it would look entirely reasonable in review. This is the thing that notices.
 *
 * Read as text rather than imported: lib/db.ts starts with `import
 * "server-only"`, which throws outside a server component.
 */
const source = readFileSync(new URL("../lib/db.ts", import.meta.url), "utf8");

test("no query that can reach a page selects the email column", () => {
  // Every select statement in the file, whatever it feeds.
  const selects = source.match(/select[\s\S]*?from\s+signups/gi) ?? [];
  assert.ok(selects.length > 0, "expected to find select statements to check");

  for (const statement of selects) {
    assert.ok(
      !/\bemail\b/i.test(statement),
      `a select against signups mentions email:\n${statement.trim()}`,
    );
  }
});

test("SignupRow has no email field", () => {
  const shape = source.match(/export type SignupRow = \{[\s\S]*?\};/);
  assert.ok(shape, "expected to find the SignupRow type");
  assert.ok(!/\bemail\b/i.test(shape[0]), "SignupRow must not carry an address");
});

test("the address is still written somewhere, or this file is guarding nothing", () => {
  assert.match(source, /update signups set email/i);
});

/**
 * Both writes stamp the time, checked in the two places an address is written.
 *
 * `email_asked_at` is what lets `npm run email:coverage` tell an address that
 * was recorded from a row that has none, and it is only trustworthy if it is
 * never written separately from the address itself. A future edit that drops it
 * from either statement would leave the column silently half true.
 */
test("every write of an address also records when it was taken", () => {
  const update = source.match(/update signups set email[\s\S]*?`/i);
  assert.ok(update, "expected to find the update that stores an address");
  assert.match(update[0], /email_asked_at\s*=\s*now\(\)/i);

  const route = readFileSync(new URL("../app/api/signups/route.ts", import.meta.url), "utf8");
  const insert = route.match(/insert into signups[\s\S]*?returning/i);
  assert.ok(insert, "expected to find the insert that creates a row");
  assert.ok(
    !/\bemail\b/.test(insert[0]) || /email_asked_at/.test(insert[0]),
    "the insert writes an address without recording when it was taken",
  );
});

/**
 * Signing in is what records the address, and a failure to record it must not
 * become a failure to sign in.
 *
 * The write lives in the `jwt` callback because /join redirects anyone who
 * already has a row, so the sign-in pass is the only code a returning person
 * runs. That is also the whole reason it has to be wrapped: an unreachable
 * database there would otherwise turn a cold Neon into a site nobody can get
 * into, to protect a mailing list.
 */
test("signing in records the address, and cannot fail because of it", () => {
  const auth = readFileSync(new URL("../auth.ts", import.meta.url), "utf8");
  assert.match(auth, /\bsaveEmail\b/, "auth.ts must save the address on sign-in");

  const call = auth.match(/try\s*\{[\s\S]*?saveEmail[\s\S]*?\}\s*catch/);
  assert.ok(call, "the saveEmail call must be inside a try/catch");
});
