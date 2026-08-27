import { auth } from "@/auth";
import { isSignatureValid, recordCoffee } from "@/lib/coffee";
import { currencyByCode, normalizeAmount, toPaise } from "@/lib/currency";
import { signupForGoogleSub } from "@/lib/db";

export const dynamic = "force-dynamic";

/**
 * The browser reporting a payment it just made, and this deciding whether to
 * believe it.
 *
 * Belief comes from the signature. Razorpay signs the order and payment ids
 * together with the key secret, which only Razorpay and this server hold, so a
 * browser cannot produce one for a payment that did not happen. Everything
 * else in the request is either recomputed here or ignored.
 *
 * Which row on the wall to mark comes from the session cookie and never from
 * the request. Somebody may pay for a coffee; nobody gets to say whose face it
 * lands on.
 *
 * The webhook writes the same row independently. This route exists because a
 * webhook can take a few seconds and the reader is looking at a spinner, and
 * because a webhook that is misconfigured should not mean nobody is ever
 * thanked. Whichever arrives first wins, and the insert is idempotent.
 */
export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "generic" }, { status: 400 });
  }
  if (typeof body !== "object" || body === null) {
    return Response.json({ error: "generic" }, { status: 400 });
  }

  const {
    razorpay_order_id: orderId,
    razorpay_payment_id: paymentId,
    razorpay_signature: signature,
    amount,
    currency: code,
  } = body as Record<string, unknown>;

  if (
    typeof orderId !== "string" ||
    typeof paymentId !== "string" ||
    typeof signature !== "string"
  ) {
    return Response.json({ error: "generic" }, { status: 400 });
  }

  if (!isSignatureValid(orderId, paymentId, signature)) {
    // Not a 403 by accident. Somebody reaching here without a valid signature
    // either did not pay or is trying it on, and both deserve the same answer.
    console.error("coffee signature rejected", { orderId, paymentId });
    return Response.json({ error: "failed" }, { status: 403 });
  }

  const currency = currencyByCode(typeof code === "string" ? code : null);
  const shown = normalizeAmount(amount, currency) ?? currency.min;

  // Who to mark, from the cookie. Signed out is a perfectly good state here:
  // the coffee is recorded with a claim token instead, and whoever holds that
  // token can attach it to their face after they join.
  let signupId: string | null = null;
  try {
    const session = await auth();
    const sub = session?.user?.id;
    if (sub) signupId = (await signupForGoogleSub(sub))?.id ?? null;
  } catch (error) {
    // A payment is not allowed to fail because sign-in did. The coffee is
    // recorded unowned and can be claimed later.
    console.error("coffee session lookup failed", error);
  }

  try {
    // `marked` comes from the row, not from what we sent it. If the webhook got
    // here first the row already existed, and whether it ended up owned is a
    // question only the database can answer.
    const { signupId: owner, claimToken } = await recordCoffee({
      signupId,
      amountPaise: toPaise(shown, currency),
      displayCurrency: currency.code,
      displayAmount: shown,
      orderId,
      paymentId,
    });
    return Response.json({ marked: owner !== null, claimToken });
  } catch (error) {
    // The money moved and we could not write it down. The browser turns this
    // into the one error message that tells them not to pay again.
    console.error("coffee record failed", error);
    return Response.json({ error: "unconfirmed" }, { status: 503 });
  }
}
