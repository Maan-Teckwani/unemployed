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
