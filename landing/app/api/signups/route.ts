import { auth } from "@/auth";
import { countSignups, db, recentSignups, signupForGoogleSub, updateSignup, type SignupRow } from "@/lib/db";
import { asGenderStrict, checkName, isValidCountry, isValidSeedInput } from "@/lib/validate";
import { CACHE, CORS, corsOptions } from "@/lib/cors";
import { ipHash, isUniqueViolation } from "@/lib/ip";
import { readLimit } from "@/lib/limit";

// Never prerender. The read is request-time by nature, and if `cacheComponents`
// is ever switched on, a board frozen at build time is a silent bug.
export const dynamic = "force-dynamic";

const MAX_PER_IP = 3;
const WINDOW_MINUTES = 10;

export async function OPTIONS() {
  // Next only auto-answers OPTIONS with an Allow header, which does not satisfy
  // a CORS preflight.
  return corsOptions();
}

/**
 * One page of the wall, plus how many people are on it.
 *
 * `count` is the whole wall, not the length of `signups`. It used to be the
 * latter, which meant the number on the page was really the page size: at two
 * hundred rows and climbing, every reader was told there were exactly two
 * hundred of them.
 *
 * `nextCursor` is null when this is the last page. Callers pass it back as
 * `?cursor=` and are not expected to look inside it.
 */
export async function GET(request: Request) {
  const params = new URL(request.url).searchParams;
  const limit = readLimit(params, { fallback: 200, max: 500 });
  const cursor = params.get("cursor");

  try {
    const [signups, count] = await Promise.all([
      recentSignups(limit, cursor),
      countSignups(),
    ]);
    return Response.json(
      {
        count,
        signups,
        // A short page is the end of the wall. A full one might not be, so it
        // carries a cursor and the next request finds out.
        nextCursor: signups.length === limit ? (signups[signups.length - 1]?.id ?? null) : null,
      },
      { headers: { ...CORS, ...CACHE } },
    );
  } catch (error) {
    console.error("board read failed", error);
    return Response.json({ error: "board unavailable" }, { status: 503, headers: CORS });
  }
}

export async function POST(request: Request) {
  // Who you are comes from the session cookie, never from the request body.
  // The browser gets to choose its display name and its face; it does not get
  // to choose whose row it is writing.
  const session = await auth();
  const googleSub = session?.user?.id;
  if (!googleSub) return fail("mustSignIn", 401);

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return fail("generic", 400);
  }
  if (typeof body !== "object" || body === null) return fail("generic", 400);

  const { name: rawName, country, gender, seed } = body as Record<string, unknown>;

  const { name, problem } = checkName(rawName);
  if (problem) return fail(problem, problem === "profane" ? 422 : 400, "name");

  if (!isValidCountry(country)) return fail("country", 400, "country");
  const chosenGender = asGenderStrict(gender);
  if (!chosenGender) return fail("generic", 400, "gender");
  if (!isValidSeedInput(seed)) return fail("generic", 400);

  // Signing in again should land you back on your own row rather than being
  // told you are rate limited, so this is checked before the insert as well as
  // being caught as a unique violation after it.
  const already = await signupForGoogleSub(googleSub);
  if (already) return Response.json(already, { status: 200, headers: CORS });

  try {
    const sql = db();
    // The rate limit lives inside the insert, so it costs no extra round trip
    // and it holds across serverless instances, where an in-memory counter
    // would count only the requests that happened to land on the same one.
    //
    // The email goes in but never comes back out: what the `returning` clause
    // hands over becomes a SignupRow, and a SignupRow is serialised into a page.
    const rows = (await sql`
      with recent as (
        select count(*)::int as n from signups
        where ip_hash = ${ipHash(request)}
          and created_at > now() - make_interval(mins => ${WINDOW_MINUTES})
      ), inserted as (
        insert into signups (name, country, gender, seed, ip_hash, google_sub, email)
        select ${name}, ${country.toUpperCase()}, ${chosenGender}, ${seed},
               ${ipHash(request)}, ${googleSub}, ${session.user?.email ?? null}
        from recent where n < ${MAX_PER_IP}
        returning id, name, country, gender, seed, created_at
      )
      select * from inserted
    `) as SignupRow[];

    if (rows.length === 0) return fail("rateLimited", 429);
    return Response.json(rows[0], { status: 201, headers: CORS });
  } catch (error) {
    // Two tabs submitting at once. A duplicate should look like success, not
    // like a failure, so hand back the row that already exists.
    if (isUniqueViolation(error)) {
      const existing = await signupForGoogleSub(googleSub);
      if (existing) return Response.json(existing, { status: 200, headers: CORS });
    }
    console.error("signup failed", error);
    return fail("generic", 503);
  }
}

export async function PUT(request: Request) {
  const session = await auth();
  const googleSub = session?.user?.id;
  if (!googleSub) return fail("mustSignIn", 401);

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return fail("generic", 400);
  }
  if (typeof body !== "object" || body === null) return fail("generic", 400);

  const { name: rawName, country, gender, seed } = body as Record<string, unknown>;

  const { name, problem } = checkName(rawName);
  if (problem) return fail(problem, problem === "profane" ? 422 : 400, "name");

  if (!isValidCountry(country)) return fail("country", 400, "country");
  const chosenGender = asGenderStrict(gender);
  if (!chosenGender) return fail("generic", 400, "gender");
  if (!isValidSeedInput(seed)) return fail("generic", 400);

  try {
    const updated = await updateSignup(googleSub, name, country.toUpperCase(), chosenGender, seed);
    if (!updated) return fail("notFound", 404);
    return Response.json(updated, { status: 200, headers: CORS });
  } catch (error) {
    console.error("signup update failed", error);
    return fail("generic", 503);
  }
}

function fail(error: string, status: number, field?: string) {
  return Response.json({ error, field }, { status, headers: CORS });
}
