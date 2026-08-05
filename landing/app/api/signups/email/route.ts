import { auth } from "@/auth";
import { settleEmailAsk } from "@/lib/db";

export const dynamic = "force-dynamic";

/**
 * The answer to "can we keep your email", from the panel on /join.
 *
 * No CORS headers, unlike the boards next door. Those are read by the local app
 * from localhost and hold nothing worth protecting; this one is a write, from
 * one page on this site, and the session cookie is what authorises it. Leaving
 * the wildcard off means the browser will not carry that cookie here from
 * anywhere else, and the cookie's own SameSite default already says the same.
 *
 * The address itself is never in the request body. It comes off the session,
 * the same way the row's owner does, so a browser can only ever say yes or no
 * about its own account and cannot nominate an address that is not its own.
 *
 * Both answers are writes. "No" records that the question was asked and leaves
 * the column null, which is the only thing that stops the panel reappearing on
 * every visit and turning a real choice into a nag.
 */
export async function POST(request: Request) {
  const session = await auth();
  const googleSub = session?.user?.id;
  if (!googleSub) return Response.json({ error: "mustSignIn" }, { status: 401 });

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "generic" }, { status: 400 });
  }
  if (typeof body !== "object" || body === null) {
    return Response.json({ error: "generic" }, { status: 400 });
  }

  const { keep } = body as Record<string, unknown>;
  if (typeof keep !== "boolean") {
    return Response.json({ error: "generic" }, { status: 400 });
  }

  // Agreeing when Google did not hand over an address is a decline in practice:
  // the ask is settled either way, and there is nothing to store.
  const email = keep ? (session.user?.email ?? null) : null;

  try {
    await settleEmailAsk(googleSub, email);
    return Response.json({ ok: true }, { status: 200 });
  } catch (error) {
    console.error("email ask failed", error);
    return Response.json({ error: "generic" }, { status: 503 });
  }
}
