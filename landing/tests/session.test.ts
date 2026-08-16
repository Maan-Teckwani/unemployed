/**
 * The sign-in decision, which is the only thing standing between a launch and
 * a wall full of rows with no address on them.
 *
 * Two failures are being guarded against, and they are not the same size. A
 * missing address costs one email and is recovered the next time that person
 * signs in. A sign-in that produces no session costs the person entirely: they
 * press the button, come back, and are still signed out. So every case where
 * the provider sends something unexpected has to end in a usable token.
 */
import { strict as assert } from "node:assert";
import { test } from "node:test";

import { identify, isCurrentEpoch, SESSION_EPOCH } from "../lib/session.ts";

// What Google actually sends, which is the case that has to keep working.
const GOOGLE = { sub: "108423", email: "someone@gmail.com" };

test("an ordinary Google profile gives both halves", () => {
  assert.deepEqual(identify(GOOGLE, null, {}), {
    sub: "108423",
    email: "someone@gmail.com",
  });
});

test("a profile with no sub falls back rather than losing the account", () => {
  const user = { id: "108423", email: "someone@gmail.com" };
  assert.deepEqual(identify({ email: "someone@gmail.com" }, user, {}), {
    sub: "108423",
    email: "someone@gmail.com",
  });
});

test("a profile with no email falls back to the one next-auth derived", () => {
  const identity = identify({ sub: "108423" }, { email: "someone@gmail.com" }, {});
  assert.equal(identity.email, "someone@gmail.com");
});

test("a returning token supplies what a thin response did not", () => {
  const token = { sub: "108423", email: "someone@gmail.com" };
  assert.deepEqual(identify(null, undefined, token), {
    sub: "108423",
    email: "someone@gmail.com",
  });
});

test("the first non-empty wins, in the order given", () => {
  const identity = identify(GOOGLE, { id: "stale", email: "stale@example.com" }, {});
  assert.deepEqual(identity, GOOGLE);
});

test("blank and whitespace claims count as absent, not as a value", () => {
  // A row owned by "" is a row no later sign-in can ever match again.
  const identity = identify({ sub: "  ", email: "" }, { id: "108423", email: " " }, {});
  assert.equal(identity.sub, "108423");
  assert.equal(identity.email, null);
});

test("nothing anywhere is null, not a crash and not an empty string", () => {
  assert.deepEqual(identify(null, undefined, {}), { sub: null, email: null });
});

test("only the current epoch is a session", () => {
  assert.equal(isCurrentEpoch({ epoch: SESSION_EPOCH }), true);
  // Everyone holding a cookie from before this change.
  assert.equal(isCurrentEpoch({}), false);
  assert.equal(isCurrentEpoch({ epoch: SESSION_EPOCH - 1 }), false);
  // A string that looks right is still not right, because the check is strict.
  assert.equal(isCurrentEpoch({ epoch: String(SESSION_EPOCH) }), false);
});
