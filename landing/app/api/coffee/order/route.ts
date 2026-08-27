import { createOrder, isConfigured, keyId } from "@/lib/coffee";
import { currencyByCode, normalizeAmount, toPaise } from "@/lib/currency";

// The order is created per request and must never be a cached one: two people
// paying the same amount would otherwise be handed the same order.
export const dynamic = "force-dynamic";

/**
 * Ask Razorpay for an order, so the browser has something to pay.
 *
 * The amount arrives from the browser and is not believed. It is snapped back
 * onto the ladder for its currency before it becomes money, so the worst a
 * crafted request can do is buy a coffee at a price the page would have offered
 * anyway. That matters less here than it would on a shop, since the failure is
 * somebody paying us the wrong amount, but a price the client can set is the
 * kind of thing that stops being harmless when the page changes.
 *
 * The currency is only ever what to display. The charge is always in rupees,
 * because that is what settles into an Indian account without a separate
 * activation. See lib/currency.ts.
 */
export async function POST(request: Request) {
  if (!isConfigured()) {
    return Response.json({ error: "unavailable" }, { status: 503 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "generic" }, { status: 400 });
  }
  if (typeof body !== "object" || body === null) {
    return Response.json({ error: "generic" }, { status: 400 });
  }

  const { amount, currency: code } = body as Record<string, unknown>;
  const currency = currencyByCode(typeof code === "string" ? code : null);
  const shown = normalizeAmount(amount, currency);
  if (shown === null) {
    return Response.json({ error: "generic" }, { status: 400 });
  }

  const amountPaise = toPaise(shown, currency);

  try {
    const order = await createOrder(amountPaise, {
      // Notes ride along to the dashboard, which is where a question about a
      // payment gets answered. Without them a row there is a rupee figure with
      // no way back to the number the person actually saw.
      // Structured rather than one string, because the webhook reads these back
      // to record what the payer was shown. It has no other way to know: it
      // arrives from Razorpay with a rupee figure and nothing else.
      shown_currency: currency.code,
      shown_amount: String(shown),
      source: "coffee",
    });
    return Response.json({
      orderId: order.id,
      amountPaise,
      currency: currency.code,
      shown,
      keyId: keyId(),
    });
  } catch (error) {
    console.error("coffee order failed", error);
    return Response.json({ error: "generic" }, { status: 503 });
  }
}
