import { isWebhookValid, recordCoffee } from "@/lib/coffee";
import { currencyByCode } from "@/lib/currency";

export const dynamic = "force-dynamic";

/**
 * Razorpay telling us a payment was captured, whether or not the browser was
 * still around to say so.
 *
 * This is the reliable half of recording a coffee, and the route in ../verify
 * is the fast half. Somebody who pays and then closes the tab, or whose phone
 * drops the connection between the bank and the return trip, still gets their
 * payment written down, because this arrives from Razorpay's servers and does
 * not care what happened to theirs.
 *
 * Point Razorpay at /api/coffee/webhook in the dashboard, subscribed to
 * `payment.captured`, and put the secret it gives you in RAZORPAY_WEBHOOK_SECRET.
 * Without that variable every delivery is rejected, which is the correct
 * behaviour for an unauthenticated endpoint that writes rows: an unconfigured
 * webhook loses the safety net, a webhook that trusts anybody loses the table.
 */
export async function POST(request: Request) {
  // The raw text, not the parsed object. The signature is over the exact bytes
  // Razorpay sent, and JSON.parse followed by JSON.stringify does not reliably
  // reproduce them: key order and number formatting are both free to change.
  const raw = await request.text();

  if (!isWebhookValid(raw, request.headers.get("x-razorpay-signature"))) {
    console.error("coffee webhook signature rejected");
    return Response.json({ error: "forbidden" }, { status: 403 });
  }

  let event: WebhookBody;
  try {
    event = JSON.parse(raw) as WebhookBody;
  } catch {
    return Response.json({ error: "bad body" }, { status: 400 });
  }

  const payment = event.payload?.payment?.entity;
  // Only captured payments, and only the ones this page started. The account is
  // shared with another product, so an unrelated capture must not turn into a
  // coffee on this wall.
  if (event.event !== "payment.captured" || !payment || payment.notes?.source !== "coffee") {
    // 200 rather than 4xx. Razorpay retries anything else for hours, and this
    // is not a failure: it is a delivery that correctly has nothing to do.
    return Response.json({ ok: true, ignored: true });
  }

  const currency = currencyByCode(payment.notes.shown_currency ?? null);
  const shownAmount = Number(payment.notes.shown_amount);

  try {
    // No signup id. This route has no session and never will, so a coffee it
    // writes is unowned and carries a claim token. If the browser makes it back
    // to ../verify afterwards, that call fills the owner in.
    await recordCoffee({
      signupId: null,
      amountPaise: payment.amount,
      displayCurrency: currency.code,
      displayAmount: Number.isFinite(shownAmount) ? shownAmount : payment.amount / 100,
      orderId: payment.order_id,
      paymentId: payment.id,
    });
    return Response.json({ ok: true });
  } catch (error) {
    // 503 on purpose, so Razorpay retries. A cold database should not cost
    // somebody their coffee.
    console.error("coffee webhook record failed", error);
    return Response.json({ error: "retry" }, { status: 503 });
  }
}

type WebhookBody = {
  event?: string;
  payload?: {
    payment?: {
      entity?: {
        id: string;
        order_id: string;
        amount: number;
        notes?: Record<string, string | undefined>;
      };
    };
  };
};
