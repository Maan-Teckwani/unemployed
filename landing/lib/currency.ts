/**
 * What a reader is shown, and what their card is actually charged.
 *
 * Those are two different numbers here, deliberately, and the page says so.
 *
 * Razorpay settles into an Indian bank account. Charging in a foreign currency
 * is a separate activation that has to be approved for the website before it
 * works, so every payment this page takes is in INR. Showing a reader in Berlin
 * a number in rupees, though, is asking them to do arithmetic before they can
 * decide whether five of something is a lot. So the ladder is priced in round
 * numbers in their own currency and the rupee figure is stated underneath it.
 *
 * The rates are written down here rather than fetched, and they are meant to be
 * roughly right rather than exactly right. What they decide is how many rupees
 * "5" is worth, on a page where the whole point is that any of these numbers is
 * fine. A rate that has drifted three percent moves the charge by a few rupees,
 * which is the correct amount of wrong for a tip jar, and in exchange there is
 * no request to make, nothing to cache, and no rate provider to be down.
 *
 * The ladders are the other half of the same idea. A reader in Tokyo should see
 * 300, 800, 1500 yen and not 118, 353 and 588, which is what converting a rupee
 * ladder into yen produces. So each currency carries its own round numbers and
 * the conversion runs the other way, at the moment of paying.
 */

export type CurrencyCode =
  | "INR"
  | "USD"
  | "EUR"
  | "GBP"
  | "AUD"
  | "CAD"
  | "SGD"
  | "AED"
  | "JPY";

export type Currency = {
  code: CurrencyCode;
  /** Written before the number. A trailing space where the code is the symbol. */
  symbol: string;
  /** Rupees to one unit of this currency. Approximate, on purpose. See above. */
  rate: number;
  /** The smallest and largest the slider goes, in this currency. */
  min: number;
  max: number;
  /** How far one notch of the slider moves. */
  step: number;
  /** The three buttons. The last one fills the cup. */
  presets: readonly [number, number, number];
};

/**
 * `max` is the full cup, and it is the same as the last preset for every
 * currency. That is what makes the top button mean something: it is the one
 * that fills it.
 */
const CURRENCIES: Record<CurrencyCode, Currency> = {
  INR: { code: "INR", symbol: "₹", rate: 1, min: 50, max: 500, step: 50, presets: [100, 300, 500] },
  USD: { code: "USD", symbol: "$", rate: 88, min: 1, max: 10, step: 1, presets: [2, 5, 10] },
  EUR: { code: "EUR", symbol: "€", rate: 96, min: 1, max: 10, step: 1, presets: [2, 5, 10] },
  GBP: { code: "GBP", symbol: "£", rate: 112, min: 1, max: 10, step: 1, presets: [2, 5, 10] },
  AUD: { code: "AUD", symbol: "A$", rate: 57, min: 2, max: 15, step: 1, presets: [3, 8, 15] },
  CAD: { code: "CAD", symbol: "C$", rate: 63, min: 2, max: 15, step: 1, presets: [3, 8, 15] },
  SGD: { code: "SGD", symbol: "S$", rate: 65, min: 2, max: 15, step: 1, presets: [3, 8, 15] },
  AED: { code: "AED", symbol: "AED ", rate: 24, min: 5, max: 40, step: 5, presets: [10, 20, 40] },
  JPY: { code: "JPY", symbol: "¥", rate: 0.57, min: 100, max: 1500, step: 100, presets: [300, 800, 1500] },
};

/**
 * Which currency a country is shown.
 *
 * Only the places that get their own ladder are in here. Everywhere else falls
 * back to USD, which is the currency someone abroad is most likely to be able
 * to read a number in without thinking about it, and which is what a card
 * statement in an unlisted country would compare against anyway.
 *
 * India is the one entry that is not a fallback decision. It is who this was
 * built for and where nearly everyone reading it is.
 */
const BY_COUNTRY: Record<string, CurrencyCode> = {
  IN: "INR",
  US: "USD",
  GB: "GBP",
  AU: "AUD",
  CA: "CAD",
  SG: "SGD",
  AE: "AED",
  JP: "JPY",
  // The euro, spelled out rather than inferred. There is no rule that turns a
  // country code into a currency, and guessing from the continent puts Poland
  // and Switzerland on a currency they do not use.
  AT: "EUR", BE: "EUR", CY: "EUR", DE: "EUR", EE: "EUR", ES: "EUR", FI: "EUR",
  FR: "EUR", GR: "EUR", HR: "EUR", IE: "EUR", IT: "EUR", LT: "EUR", LU: "EUR",
  LV: "EUR", MT: "EUR", NL: "EUR", PT: "EUR", SI: "EUR", SK: "EUR",
};

export const DEFAULT_CURRENCY: CurrencyCode = "INR";

/** The one currency anyone outside the list above is priced in. */
const FOREIGN_FALLBACK: CurrencyCode = "USD";

/**
 * The currency for an ISO country code, which is what the geo header carries.
 *
 * An absent header is not an unknown country, it is a request that never went
 * through a CDN: local development, or a preview opened directly. Rupees is the
 * right answer there rather than dollars.
 */
export function currencyForCountry(country: string | null | undefined): Currency {
  if (!country) return CURRENCIES[DEFAULT_CURRENCY];
  const code = BY_COUNTRY[country.toUpperCase()] ?? FOREIGN_FALLBACK;
  return CURRENCIES[code];
}

export function currencyByCode(code: string | null | undefined): Currency {
  const known = code && code.toUpperCase() in CURRENCIES;
  return CURRENCIES[known ? (code!.toUpperCase() as CurrencyCode) : DEFAULT_CURRENCY];
}

/**
 * A number, written the way that currency writes it.
 *
 * The locale is pinned rather than taken from the reader, because this runs on
 * the server and again in the browser and the two have to produce the same
 * string. A number formatted one way in the HTML and another way at hydration
 * is a React mismatch and a visible flicker.
 *
 * Whole amounts lose their decimals. Every rung of every ladder is whole, so
 * this is really about the slider, and "$5" reads better than "$5.00" on a
 * button.
 */
export function formatMoney(amount: number, currency: Currency): string {
  const digits = Number.isInteger(amount) ? 0 : 2;
  const number = new Intl.NumberFormat("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(amount);
  return `${currency.symbol}${number}`;
}

/**
 * What the card is charged, in paise, for an amount in the shown currency.
 *
 * Rounded to a whole rupee before it becomes paise, so the amount on the
 * statement is a number a person would write down. Razorpay takes an integer
 * count of the smallest unit and would happily charge 449.6 paise of nothing.
 */
export function toPaise(amount: number, currency: Currency): number {
  return Math.round(amount * currency.rate) * 100;
}

/** The same figure as rupees, for the line that says what will be charged. */
export function toRupees(amount: number, currency: Currency): number {
  return Math.round(amount * currency.rate);
}

/**
 * A rupee figure, written out.
 *
 * Its own function because the one place that needs it is telling a reader in
 * another currency what their card will be charged, and that sentence needs
 * rupees regardless of which ladder they are looking at.
 */
export function formatRupees(rupees: number): string {
  return formatMoney(rupees, CURRENCIES.INR);
}

/**
 * Snap an amount onto the ladder it came from.
 *
 * The browser sends a number and the server has to decide what to charge for
 * it, which means it cannot be trusted to be one of the ones we offered. This
 * clamps it into range and onto a step, so the worst a crafted request can do
 * is buy a coffee at a price we would have shown anyway.
 */
export function normalizeAmount(raw: unknown, currency: Currency): number | null {
  // Refused by type before it is refused by value, because coercion is where
  // this goes wrong. `Number(null)` is 0, `Number([])` is 0, `Number("")` is 0,
  // and 0 is finite, so a body that never named an amount would sail through
  // the "is this a number" check and come out the far end clamped to the
  // cheapest coffee on the ladder, looking entirely healthy. This is the same
  // trap readLimit in lib/limit.ts exists because of.
  if (typeof raw !== "number" && typeof raw !== "string") return null;
  if (typeof raw === "string" && raw.trim() === "") return null;

  const value = Number(raw);
  if (!Number.isFinite(value)) return null;
  const stepped = Math.round(value / currency.step) * currency.step;
  const clamped = Math.min(Math.max(stepped, currency.min), currency.max);
  // Floating point: 0.1 sized steps would land on 2.9000000000000004 here, and
  // that number goes into the database and onto a receipt.
  return Math.round(clamped * 100) / 100;
}

/**
 * How full the cup is, for an amount.
 *
 * Never quite empty at the bottom of the slider. A cup with nothing in it reads
 * as broken rather than as cheap, and the smallest rung is still a coffee.
 */
export function fillFor(amount: number, currency: Currency): number {
  const span = currency.max - currency.min;
  const share = span <= 0 ? 1 : (amount - currency.min) / span;
  return Math.min(Math.max(0.12 + share * 0.88, 0.12), 1);
}
