import assert from "node:assert/strict";
import test from "node:test";

import { CONTRIBUTOR_IDS, MAKER_ID, PINNED_IDS, highlightFor } from "../lib/contributors.ts";
import { orderWall } from "../lib/wall-order.ts";
import type { SignupRow } from "../lib/db.ts";

function person(id: string): SignupRow {
  return {
    id,
    name: `Person ${id}`,
    country: "IN",
    gender: "male",
    seed: `seed-${id}`,
    created_at: "2026-08-01 00:00:00+00",
  };
}

const maker = person(MAKER_ID);
const contributor = person(CONTRIBUTOR_IDS[0]);

test("a visitor who is nobody special still sees the makers first", () => {
  const order = orderWall({
    me: null,
    pinned: [maker, contributor],
    rows: [person("900"), person("901")],
  });
  assert.deepEqual(
    order.map((p) => p.id),
    [MAKER_ID, CONTRIBUTOR_IDS[0], "900", "901"],
  );
});

test("you come first, and the makers sit beside you", () => {
  const me = person("500");
  const order = orderWall({
    me,
    pinned: [maker, contributor],
    rows: [person("900"), me],
  });
  assert.deepEqual(
    order.map((p) => p.id),
    ["500", MAKER_ID, CONTRIBUTOR_IDS[0], "900"],
  );
});

test("a pinned person deep in the wall is moved, not copied", () => {
  const order = orderWall({
    me: null,
    pinned: [contributor],
    rows: [person("900"), contributor, person("901")],
  });
  assert.deepEqual(
    order.map((p) => p.id),
    [CONTRIBUTOR_IDS[0], "900", "901"],
  );
});

test("being the maker yourself is one face, not two", () => {
  const order = orderWall({ me: maker, pinned: [maker, contributor], rows: [maker] });
  assert.deepEqual(
    order.map((p) => p.id),
    [MAKER_ID, CONTRIBUTOR_IDS[0]],
  );
});

test("people who joined during the visit come after the makers", () => {
  const fresh = person("999");
  const order = orderWall({
    me: null,
    pinned: [maker],
    added: [fresh],
    rows: [person("900")],
  });
  assert.deepEqual(
    order.map((p) => p.id),
    [MAKER_ID, "999", "900"],
  );
});

test("an empty pinned list leaves the wall exactly as it was", () => {
  const rows = [person("900"), person("901")];
  assert.deepEqual(
    orderWall({ me: null, pinned: [], rows }).map((p) => p.id),
    ["900", "901"],
  );
});

test("highlightFor names the two tiers and nobody else", () => {
  assert.equal(highlightFor(MAKER_ID), "maker");
  assert.equal(highlightFor(CONTRIBUTOR_IDS[0]), "contributor");
  assert.equal(highlightFor("900"), null);
  // Ids arrive from the driver as strings, but a number must not silently miss.
  assert.equal(highlightFor(Number(MAKER_ID)), "maker");
});

test("the maker leads the pinned list", () => {
  assert.equal(PINNED_IDS[0], MAKER_ID);
  assert.equal(new Set(PINNED_IDS).size, PINNED_IDS.length);
});
