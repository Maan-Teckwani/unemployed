"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

import { CoffeeCup } from "./coffee-cup";
import { copy } from "@/lib/copy";
import { fillFor, formatMoney, formatRupees, toRupees, type Currency } from "@/lib/currency";

/**
 * The cup, the amount, and the button that turns one into the other.
 *
 * The whole of the payment lives in this one component rather than being spread
 * across a hook and a context, because it is a single linear thing: pick a
 * number, ask the server for an order, open Razorpay, tell the server what came
 * back. Splitting it would only make the order of those four steps harder to
 * see.
 *
 * The Razorpay script is fetched when the button is pressed and not before.
 * Everybody who opens this page would otherwise pay for a third party script,
 * on a site whose entire pitch is that it does not send your things anywhere.
 */

/** Where a coffee bought signed out waits for a face to attach itself to. */
const CLAIM_KEY = "coffee-claim";

type Status = "idle" | "opening" | "confirming" | "done";
type ErrorKey = keyof typeof copy.coffee.errors;

export function CoffeeForm({
  currency,
  configured,
  onWall,
  name,
}: {
  currency: Currency;
  /** Whether the server has Razorpay keys. Without them there is no button. */
  configured: boolean;
  /** Signed in with a row on the wall, which is what can carry a ring. */
  onWall: boolean;
  /** Their name, to prefill the checkout. */
  name: string | null;
}) {
  const [amount, setAmount] = useState<number>(currency.presets[1]);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<ErrorKey | null>(null);
  const [marked, setMarked] = useState(false);
  const [claimed, setClaimed] = useState(false);

  // Razorpay calls `ondismiss` when the window closes, which includes the close
  // that follows a successful payment. Without this the thank you screen would
  // be replaced by "payment window closed, nothing was charged" a moment after
  // somebody paid, which is the worst sentence on this page to show by mistake.
  const settled = useRef(false);

  const shown = formatMoney(amount, currency);
  const foreign = currency.code !== "INR";

  /**
   * A coffee bought signed out, attaching itself once there is a face to attach
   * to. Runs on every visit to this page rather than only after paying, because
   * the join it is waiting for happens on a different page and often on a
   * different day.
   */
  useEffect(() => {
    if (!onWall) return;
    let token: string | null = null;
    try {
      token = localStorage.getItem(CLAIM_KEY);
    } catch {
      // Storage denied. There is nothing to claim and nothing to report.
    }
    if (!token) return;

    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/coffee/claim", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ token }),
        });
        if (!res.ok) return;
        const data = (await res.json()) as { claimed?: boolean };
        // Spent, or already spent by another tab. Either way it is no longer
        // worth carrying around.
        try {
          localStorage.removeItem(CLAIM_KEY);
        } catch {}
        if (data.claimed && !cancelled) setClaimed(true);
      } catch {
        // The token stays put and the next visit tries again.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [onWall]);

  const pay = useCallback(async () => {
    if (!configured) return setError("unavailable");
    setError(null);
    setStatus("opening");
    settled.current = false;

    try {
      const res = await fetch("/api/coffee/order", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ amount, currency: currency.code }),
      });
      if (!res.ok) {
        const data = (await res.json().catch(() => ({}))) as { error?: ErrorKey };
        throw new ExpectedFailure(data.error ?? "generic");
      }
      const order = (await res.json()) as {
        orderId: string;
        amountPaise: number;
        keyId: string;
      };

      await loadCheckout();

      const checkout = new window.Razorpay!({
        key: order.keyId,
        amount: order.amountPaise,
        currency: "INR",
        order_id: order.orderId,
        name: copy.meta.title,
        description: `${copy.meta.pages.coffee}, ${shown}`,
        prefill: name ? { name } : undefined,
        // The one place a Razorpay colour is set. Their window is their window,
        // but it opens over this page and arriving in default blue reads as a
        // different site having taken over.
        theme: { color: "#6b4a2f" },
        modal: {
          ondismiss: () => {
            if (settled.current) return;
            setStatus("idle");
            setError("dismissed");
          },
        },
        handler: async (response: RazorpayResponse) => {
          settled.current = true;
          setStatus("confirming");
          try {
            const check = await fetch("/api/coffee/verify", {
              method: "POST",
              headers: { "content-type": "application/json" },
              body: JSON.stringify({ ...response, amount, currency: currency.code }),
            });
            const data = (await check.json().catch(() => ({}))) as {
              marked?: boolean;
              claimToken?: string | null;
              error?: ErrorKey;
            };
            if (!check.ok) {
              // They have paid. Whatever went wrong here, the screen must not
              // suggest trying again.
              setStatus("done");
              setError(data.error ?? "unconfirmed");
              return;
            }
            setMarked(Boolean(data.marked));
            if (data.claimToken) {
              try {
                localStorage.setItem(CLAIM_KEY, data.claimToken);
              } catch {
                // Storage denied, so the coffee stays unattached. The payment
                // itself is recorded either way, which is the part that matters.
              }
            }
            setStatus("done");
          } catch {
            setStatus("done");
            setError("unconfirmed");
          }
        },
      });

      checkout.on("payment.failed", () => {
        settled.current = true;
        setStatus("idle");
        setError("failed");
      });
      checkout.open();
    } catch (failure) {
      setStatus("idle");
      setError(failure instanceof ExpectedFailure ? failure.key : "generic");
    }
  }, [amount, configured, currency.code, name, shown]);

  const drunk = status === "done" && error === null;

  return (
    <div className="grid gap-6 md:grid-cols-12 md:items-center md:gap-10">
      <div className="mx-auto w-full max-w-[13.5rem] sm:max-w-[17rem] md:col-span-5 md:max-w-[19rem]">
        <CoffeeCup fill={fillFor(amount, currency)} emptied={drunk} />
      </div>

      <div className="md:col-span-6 md:col-start-7">
        {status === "done" ? (
          <ThankYou marked={marked} error={error} />
        ) : (
          <>
            <p className="text-muted-foreground font-mono text-[11px] tracking-[0.2em] uppercase">
              {copy.coffee.amount.label}
            </p>

            <p className="mt-3 font-serif text-4xl tabular-nums sm:text-5xl">{shown}</p>
            <p className="text-muted-foreground mt-2 text-sm">{coversFor(amount, currency)}</p>

            <div className="mt-6 flex flex-wrap gap-2">
              {currency.presets.map((preset) => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => setAmount(preset)}
                  aria-pressed={amount === preset}
                  className={`rounded-lg border px-4 py-2 text-sm font-medium tabular-nums transition-colors focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none ${
                    amount === preset
                      ? "border-foreground bg-foreground text-background"
                      : "hover:bg-muted"
                  }`}
                >
                  {formatMoney(preset, currency)}
                </button>
              ))}
            </div>

            <input
              type="range"
              className="coffee-slider mt-5"
              min={currency.min}
              max={currency.max}
              step={currency.step}
              value={amount}
              aria-label={copy.coffee.amount.slider}
              onChange={(e) => setAmount(Number(e.target.value))}
            />

            {foreign && (
              <p className="text-muted-foreground mt-4 text-xs leading-relaxed">
                {copy.coffee.amount.charged(formatRupees(toRupees(amount, currency)))}
              </p>
            )}

            <button
              type="button"
              onClick={pay}
              disabled={!configured || status !== "idle"}
              className="btn-solid mt-6 w-full disabled:opacity-60"
            >
              {status === "opening"
                ? copy.coffee.amount.working
                : status === "confirming"
                  ? copy.coffee.amount.confirming
                  : copy.coffee.amount.cta(shown)}
            </button>

            {/* A disabled button with nothing beside it is a dead end nobody
                can diagnose. The button can only be pressed when there are keys,
                so without this the sentence explaining why would never appear. */}
            {(error || !configured) && (
              <p role="status" className="mt-3 text-sm font-medium">
                {copy.coffee.errors[error ?? "unavailable"]}
              </p>
            )}

            <p className="text-muted-foreground mt-5 border-t pt-4 text-xs leading-relaxed">
              {onWall ? copy.coffee.ring.signedIn : copy.coffee.ring.signedOut}
              {!onWall && (
                <>
                  {" "}
                  <Link href="/join" className="text-foreground underline underline-offset-4">
                    {copy.coffee.ring.joinCta}
                  </Link>
                </>
              )}
            </p>

            {claimed && (
              <p className="mt-3 text-sm font-medium">{copy.coffee.thanks.claimed}</p>
            )}
          </>
        )}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */

function ThankYou({ marked, error }: { marked: boolean; error: ErrorKey | null }) {
  return (
    <div role="status">
      <p className="text-muted-foreground font-mono text-[11px] tracking-[0.2em] uppercase">
        {copy.coffee.label}
      </p>
      <h2 className="mt-4 font-serif text-4xl leading-tight">{copy.coffee.thanks.heading}</h2>
      <p className="mt-5 text-base leading-relaxed">{copy.coffee.thanks.body}</p>

      {/* Money moved and the wall did not hear about it. Said plainly, and said
          instead of the cheerful line about rings, because the one thing this
          person needs to know is that they must not pay again. */}
      {error ? (
        <p className="mt-5 rounded-lg border p-4 text-sm leading-relaxed">
          {copy.coffee.errors[error]}
        </p>
      ) : (
        <p className="text-muted-foreground mt-4 text-base leading-relaxed">
          {marked ? copy.coffee.thanks.marked : copy.coffee.thanks.claimable}
        </p>
      )}

      <div className="mt-7 flex flex-wrap gap-3">
        <Link href="/wall" className="btn-solid">
          {copy.coffee.thanks.wallCta}
        </Link>
        {!marked && !error && (
          <Link href="/join" className="btn-outline">
            {copy.coffee.thanks.joinCta}
          </Link>
        )}
      </div>
    </div>
  );
}

/**
 * Which of the three sentences about what this covers belongs to an amount.
 *
 * By the ladder rather than by a rupee figure, so the sentence lines up with the
 * button the reader just pressed whatever currency they are in.
 */
function coversFor(amount: number, currency: Currency): string {
  const [small, middle] = currency.presets;
  if (amount <= small) return copy.coffee.amount.covers[0];
  if (amount <= middle) return copy.coffee.amount.covers[1];
  return copy.coffee.amount.covers[2];
}

/** An error we already have a sentence for, as opposed to one we do not. */
class ExpectedFailure extends Error {
  constructor(public key: ErrorKey) {
    super(key);
  }
}

/**
 * Razorpay's checkout, fetched the first time somebody actually wants to pay.
 *
 * Resolved from the existing global on a second press, so changing your mind
 * about the amount and pressing again does not add a second copy of the script
 * to the page.
 */
function loadCheckout(): Promise<void> {
  if (typeof window !== "undefined" && window.Razorpay) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new ExpectedFailure("generic"));
    document.head.appendChild(script);
  });
}

type RazorpayResponse = {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
};

type RazorpayInstance = {
  open: () => void;
  on: (event: string, handler: () => void) => void;
};

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => RazorpayInstance;
  }
}
