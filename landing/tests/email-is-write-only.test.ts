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
 * The consent invariant, checked in the two places an address is written.
 *
 * An address with no record of having asked for it is the exact failure this
 * whole change was about: the old code took one from every returning user on a
 * page they were redirected past. Both writes now carry `email_asked_at`, and
 * a future edit that drops it would restore the old behaviour silently.
 */
test("every write of an address also records that we asked", () => {
  const update = source.match(/update signups set email[\s\S]*?`/i);
  assert.ok(update, "expected to find the update that stores an address");
  assert.match(update[0], /email_asked_at\s*=\s*now\(\)/i);

  const route = readFileSync(new URL("../app/api/signups/route.ts", import.meta.url), "utf8");
  const insert = route.match(/insert into signups[\s\S]*?returning/i);
  assert.ok(insert, "expected to find the insert that creates a row");
  assert.ok(
    !/\bemail\b/.test(insert[0]) || /email_asked_at/.test(insert[0]),
    "the insert writes an address without recording that we asked",
  );
});

/**
 * The `jwt` callback is not allowed to touch the database again.
 *
 * It used to, and that is how addresses were collected from people who never
 * saw the disclosure: /join redirects anyone with a row, so the sign-in pass
 * was the only code they ran. Asking belongs on a page with a button on it.
 */
test("signing in does not write anything by itself", () => {
  const auth = readFileSync(new URL("../auth.ts", import.meta.url), "utf8");
  assert.ok(!/from "@\/lib\/db"/.test(auth), "auth.ts must not import the database");
  assert.ok(!/\bsettleEmailAsk\b/.test(auth), "auth.ts must not settle the email ask");
});
