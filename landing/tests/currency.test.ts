import assert from "node:assert/strict";
import { test } from "node:test";

import {
  currencyByCode,
  currencyForCountry,
  fillFor,
  formatMoney,
  formatRupees,
  normalizeAmount,
  toPaise,
  toRupees,
} from "../lib/currency.ts";

const inr = currencyByCode("INR");
const usd = currencyByCode("USD");

/**
 * The amount arrives from a browser and turns into money, so the thing worth
 * testing is what happens when the browser sends something the page could not
 * have produced.
 */
test("an amount from the browser is clamped into range", () => {
  assert.equal(normalizeAmount(999999, usd), usd.max);
  assert.equal(normalizeAmount(-40, usd), usd.min);
  assert.equal(normalizeAmount(0, inr), inr.min);
});

test("an amount that is not a number is refused rather than defaulted", () => {
  // Null matters on its own. `Number(null)` is 0 and 0 is finite, which is the
  // same trap lib/limit.ts exists because of, and here it would silently charge
  // the minimum for a request that never named an amount.
  assert.equal(normalizeAmount(null, inr), null);
  assert.equal(normalizeAmount("not a number", inr), null);
  assert.equal(normalizeAmount(undefined, inr), null);
  assert.equal(normalizeAmount(Number.NaN, inr), null);
  assert.equal(normalizeAmount(Infinity, inr), null);
});

test("a numeric string is accepted, since JSON is not typed", () => {
  assert.equal(normalizeAmount("5", usd), 5);
});

test("an amount between two steps is snapped onto one", () => {
  assert.equal(normalizeAmount(137, inr), 150);
  assert.equal(normalizeAmount(3.4, usd), 3);
});

test("the charge is always a whole number of paise", () => {
  for (const code of ["INR", "USD", "EUR", "GBP", "AUD", "CAD", "SGD", "AED", "JPY"]) {
    const currency = currencyByCode(code);
    for (const preset of currency.presets) {
      const paise = toPaise(preset, currency);
      assert.ok(Number.isInteger(paise), `${code} ${preset} gave ${paise}`);
      assert.ok(paise > 0, `${code} ${preset} is not worth anything`);
      // Razorpay would take a fractional rupee happily and it would appear on
      // somebody's statement as 449.6, so this is the one that matters.
      assert.equal(paise % 100, 0, `${code} ${preset} is not a whole rupee`);
    }
  }
});

test("what is charged is what the page said would be charged", () => {
  // The sentence under a foreign amount is built from toRupees and the charge
  // from toPaise. If those two ever disagree the page lies about the price.
  for (const code of ["USD", "EUR", "GBP", "JPY"]) {
    const currency = currencyByCode(code);
    for (const preset of currency.presets) {
      assert.equal(toPaise(preset, currency), toRupees(preset, currency) * 100);
    }
  }
});

test("the top preset fills the cup, in every currency", () => {
  // The copy says the last button is the one that fills it, and lib/currency
  // is where that stops being true if a ladder is edited carelessly.
  for (const code of ["INR", "USD", "EUR", "GBP", "AUD", "CAD", "SGD", "AED", "JPY"]) {
    const currency = currencyByCode(code);
    assert.equal(currency.presets[2], currency.max, `${code} tops out below its last preset`);
    assert.equal(fillFor(currency.max, currency), 1);
  }
});

test("the cup is never empty while there is an amount on it", () => {
  assert.ok(fillFor(inr.min, inr) > 0, "the smallest coffee draws an empty mug");
  assert.ok(fillFor(inr.min, inr) < fillFor(inr.max, inr));
});

test("a missing geo header is India, not an unknown country", () => {
  // Absent means the request never went through the CDN, which is local
  // development, and rupees is the right answer there. Dollars would be a
  // guess dressed up as a detection.
  assert.equal(currencyForCountry(null).code, "INR");
  assert.equal(currencyForCountry(undefined).code, "INR");
  assert.equal(currencyForCountry("").code, "INR");
});

test("a country nobody wrote a ladder for is priced in dollars", () => {
  assert.equal(currencyForCountry("BR").code, "USD");
  assert.equal(currencyForCountry("ZA").code, "USD");
});

test("the country code is read whatever case it arrives in", () => {
  assert.equal(currencyForCountry("de").code, "EUR");
  assert.equal(currencyForCountry("DE").code, "EUR");
});

test("an unknown currency code falls back rather than crashing", () => {
  // This one comes off the wire, from a request body, so it can be anything.
  assert.equal(currencyByCode("XYZ").code, "INR");
  assert.equal(currencyByCode(null).code, "INR");
  assert.equal(currencyByCode("usd").code, "USD");
});

test("money is written the same way on the server and in the browser", () => {
  // Pinned locale, so the string in the HTML matches the one React renders at
  // hydration. A mismatch here is a warning and a visible flicker on the price.
  assert.equal(formatMoney(1000, inr), "₹1,000");
  assert.equal(formatMoney(5, usd), "$5");
  assert.equal(formatMoney(2.5, usd), "$2.50");
  assert.equal(formatRupees(440), "₹440");
});
