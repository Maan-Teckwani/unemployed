import { auth } from "@/auth";
import { claimCoffee } from "@/lib/coffee";
import { signupForGoogleSub } from "@/lib/db";

export const dynamic = "force-dynamic";

/**
 * Attaching a coffee that was bought signed out to the face of whoever has
 * since joined the wall.
 *
 * The token is handed to the browser once, on the success screen, and kept in
 * its own localStorage. It is the only way back to an unclaimed row, and it is
 * spent the first time it works.
 *
 * Whose face it lands on comes from the session and never from the request, the
 * same rule every other write here follows. So the worst somebody who steals a
 * token can do is put a ring on their own face for a coffee they did not buy,
 * once. That is a fair trade for not making people sign in before they are
 * allowed to give you money.
 */
export async function POST(request: Request) {
  const session = await auth();
  const sub = session?.user?.id;
  if (!sub) return Response.json({ error: "mustSignIn" }, { status: 401 });

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "generic" }, { status: 400 });
  }
  const token = (body as { token?: unknown })?.token;
  if (typeof token !== "string" || token.length === 0 || token.length > 64) {
    return Response.json({ error: "generic" }, { status: 400 });
  }

  try {
    const signup = await signupForGoogleSub(sub);
    // Signed in but not on the wall. There is no face to mark yet, so the token
    // stays valid and they can come back once they have finished joining.
    if (!signup) return Response.json({ error: "mustJoinWall" }, { status: 409 });

    return Response.json({ claimed: await claimCoffee(token, signup.id) });
  } catch (error) {
    console.error("coffee claim failed", error);
    return Response.json({ error: "generic" }, { status: 503 });
  }
}
