import "server-only";

import { createHmac, randomUUID, timingSafeEqual } from "node:crypto";

import { db } from "./db";

/**
 * Taking a coffee, and being sure one was actually paid for.
 *
 * There is no Razorpay package in package.json and there does not need to be.
 * The whole of what this uses is one POST to create an order and one HMAC to
 * check a signature, and node has both. A dependency here would be a hundred
 * kilobytes and a supply chain, for an API call.
 *
 * The rule the rest of this file exists to enforce: a row in `coffees` means
 * Razorpay confirmed a payment, never that a browser said so. The browser is
 * the one party to a payment with a reason to lie, so its word is checked
 * against a signature only Razorpay and this server can produce, and the
 * webhook writes the same row independently in case the browser goes away
 * before it can report back.
 */

const API = "https://api.razorpay.com/v1";

/** The key id is public. It ships to the browser to open the checkout. */
export function keyId(): string | null {
  return process.env.RAZORPAY_KEY_ID ?? null;
}

function keySecret(): string | null {
  return process.env.RAZORPAY_KEY_SECRET ?? null;
}

/**
 * Whether payments can be taken at all.
 *
 * Checked before the page renders a pay button, so a deployment without keys
 * shows an honest "not accepting these right now" instead of a button that
 * fails when it is pressed. Local development without keys is the common case.
 */
export function isConfigured(): boolean {
  return Boolean(keyId() && keySecret());
}

function authHeader(): string {
  return `Basic ${Buffer.from(`${keyId()}:${keySecret()}`).toString("base64")}`;
}

export type Order = { id: string; amount: number };

/**
 * Ask Razorpay for an order to attach a payment to.
 *
 * The amount is fixed here, on the server, and the checkout that opens in the
 * browser can only pay the order it is given. That is the reason to create one
 * at all rather than passing an amount straight to the checkout: it takes the
 * price out of the browser's hands.
 */
export async function createOrder(amountPaise: number, notes: Record<string, string>): Promise<Order> {
  const res = await fetch(`${API}/orders`, {
    method: "POST",
    headers: { "content-type": "application/json", authorization: authHeader() },
    body: JSON.stringify({
      amount: amountPaise,
      currency: "INR",
      // Razorpay caps this at forty characters and rejects the request if it is
      // longer, which is a confusing 400 to debug from the other side.
      receipt: `coffee_${Date.now()}`,
      notes,
    }),
  });

  if (!res.ok) {
    throw new Error(`razorpay order failed: ${res.status} ${await res.text()}`);
  }
  return (await res.json()) as Order;
}

/**
 * Did Razorpay sign this payment, or did somebody type it into the console?
 *
 * Compared byte by byte in constant time. A plain `===` on a signature leaks
 * how much of a guess was right through how long the comparison took, which is
 * the one bug in this file that would not look like a bug.
 */
export function isSignatureValid(orderId: string, paymentId: string, signature: string): boolean {
  const secret = keySecret();
  if (!secret) return false;
  return sameDigest(createHmac("sha256", secret).update(`${orderId}|${paymentId}`).digest("hex"), signature);
}

/** The same check for a webhook, which signs its whole body with its own secret. */
export function isWebhookValid(rawBody: string, signature: string | null): boolean {
  const secret = process.env.RAZORPAY_WEBHOOK_SECRET;
  if (!secret || !signature) return false;
  return sameDigest(createHmac("sha256", secret).update(rawBody).digest("hex"), signature);
}

function sameDigest(expected: string, given: string): boolean {
  const a = Buffer.from(expected, "utf8");
  const b = Buffer.from(given, "utf8");
  // timingSafeEqual throws on a length mismatch rather than returning false,
  // and a wrong length is a wrong signature.
  return a.length === b.length && timingSafeEqual(a, b);
}

export type CoffeeInput = {
  signupId: string | null;
  amountPaise: number;
  displayCurrency: string;
  displayAmount: number;
  orderId: string;
  paymentId: string;
};

/**
 * Write down a confirmed payment, once.
 *
 * The browser and the webhook both call this for the same payment, in whichever
 * order they arrive, so this has to be idempotent rather than merely unlikely
 * to collide. The unique index on the payment id is what makes the second call
 * land on the conflict branch instead of writing a second row.
 *
 * It is an upsert rather than `do nothing` because of which caller arrives
 * first. Only the browser knows whose session paid; the webhook never does. If
 * the webhook wins the race, `do nothing` would leave the coffee permanently
 * unowned and the person who paid while signed in would never get their ring.
 * So an owner can be filled in later, and only later: `coalesce` keeps the one
 * already on the row, so a second call can never move a coffee off the face it
 * landed on.
 *
 * The claim token is cleared the moment the row has an owner, because there is
 * then nothing left to claim.
 */
export async function recordCoffee(
  input: CoffeeInput,
): Promise<{ signupId: string | null; claimToken: string | null }> {
  const sql = db();
  const token = input.signupId ? null : randomUUID();
  const rows = (await sql`
    insert into coffees (
      signup_id, amount_paise, display_currency, display_amount,
      razorpay_order_id, razorpay_payment_id, claim_token
    )
    values (
      ${input.signupId}::bigint, ${input.amountPaise}, ${input.displayCurrency},
      ${input.displayAmount}, ${input.orderId}, ${input.paymentId}, ${token}
    )
    on conflict (razorpay_payment_id) do update
      set signup_id = coalesce(coffees.signup_id, excluded.signup_id),
          claim_token = case
            when coalesce(coffees.signup_id, excluded.signup_id) is null
              then coffees.claim_token
            else null
          end
    returning signup_id, claim_token
  `) as { signup_id: string | null; claim_token: string | null }[];

  const row = rows[0];
  return {
    signupId: row?.signup_id ? String(row.signup_id) : null,
    claimToken: row?.claim_token ?? null,
  };
}

/**
 * Attach a coffee that was paid for signed out to the row of whoever just
 * joined, so the ring they were promised turns up.
 *
 * `claim_token is not null` in the where clause is what makes a token single
 * use: the update clears it, so replaying the same request finds nothing. And
 * `signup_id is null` means a coffee that already found its owner cannot be
 * moved by anybody who learns the token afterwards.
 */
export async function claimCoffee(token: string, signupId: string): Promise<boolean> {
  const sql = db();
  const rows = (await sql`
    update coffees
    set signup_id = ${signupId}::bigint, claim_token = null
    where claim_token = ${token} and signup_id is null
    returning id
  `) as { id: string }[];
  return rows.length > 0;
}
