import "server-only";

import { neon } from "@neondatabase/serverless";

/**
 * The one connection to Neon.
 *
 * Resolved lazily rather than at import time so a build without `DATABASE_URL`
 * still succeeds. Nothing is prerendered that touches the database, so the
 * variable is only ever needed while serving a real request.
 */
let client: ReturnType<typeof neon> | null = null;

export function db() {
  const url = process.env.DATABASE_URL;
  if (!url) throw new Error("DATABASE_URL is not set");
  client ??= neon(url);
  return client;
}

/**
 * A row as the rest of the site is allowed to see it.
 *
 * There is deliberately no `email` here, and no read query below selects one.
 * This type is handed to client components, which means every field on it is
 * serialised into the HTML that goes to whoever is looking at the page. The
 * address is written by `settleEmailAsk` and read by nothing.
 */
export type SignupRow = {
  // bigint, which the driver hands back as a string rather than a number.
  id: string;
  name: string;
  country: string;
  gender: "female" | "male" | "neutral";
  seed: string;
  created_at: string;
};

/**
 * Newest first, one page at a time.
 *
 * `after` is the id of the last row of the previous page. Paging by a key
 * rather than by `offset` matters here because people join while you are
 * scrolling: an offset of 200 means something different a minute later, so the
 * next page would repeat faces and skip others. A key means "everything older
 * than this row", which stays true no matter who joins in between.
 *
 * The cursor is only an id, but the sort is `created_at desc, id desc`, so the
 * subquery looks the row's timestamp back up rather than making the caller
 * carry it. An id that no longer exists makes the comparison null, which ends
 * the paging quietly instead of erroring.
 */
export async function recentSignups(limit = 200, after?: string | null): Promise<SignupRow[]> {
  const sql = db();
  const cursor = after ?? null;
  const rows = await sql`
    select id, name, country, gender, seed, created_at
    from signups
    where ${cursor}::bigint is null
       or (created_at, id) < (
            (select created_at from signups where id = ${cursor}::bigint),
            ${cursor}::bigint
          )
    order by created_at desc, id desc
    limit ${limit}
  `;
  return rows as SignupRow[];
}

/**
 * How many people are on the wall, which is not the same as how many were sent
 * to the browser. The page ships one page of faces and this number, so the
 * count is the truth even when the wall has more people on it than any one
 * request would ever load.
 */
export async function countSignups(): Promise<number> {
  const sql = db();
  const rows = (await sql`select count(*)::int as total from signups`) as { total: number }[];
  return rows[0]?.total ?? 0;
}

/** What a page that draws faces needs: some of the wall, and the size of it. */
export type CrowdPage = {
  people: SignupRow[];
  /** Everyone on the wall, not everyone in `people`. */
  total: number;
  /** Passed back as `?cursor=` for the next page. Null when there is no next page. */
  cursor: string | null;
};

/** How many faces the server sends before the browser has to ask for more. */
export const CROWD_PAGE = 200;

/**
 * The first page of the wall and the real headcount, for the hero and for the
 * wall page.
 *
 * An unreachable database is an empty wall rather than an error page: the rest
 * of the page is still worth reading without the faces on it, which is the same
 * call every other read here makes.
 */
export async function crowdPage(): Promise<CrowdPage> {
  try {
    const [people, total] = await Promise.all([recentSignups(CROWD_PAGE), countSignups()]);
    return {
      people,
      total,
      cursor: people.length === CROWD_PAGE ? (people[people.length - 1]?.id ?? null) : null,
    };
  } catch (error) {
    console.error("wall unavailable", error);
    return { people: [], total: 0, cursor: null };
  }
}

export type ExperienceRound = {
  round_number: number;
  round_type: string;
  description: string;
  outcome: string;
};

export type ExperienceRow = {
  id: string;
  company: string;
  role: string;
  result: string;
  summary: string;
  created_at: string;
  // Who posted it. `signup_id` is what lets the wall ask for one person's
  // experiences without loading everyone's and filtering in the browser.
  signup_id: string;
  name: string;
  seed: string;
  gender: "female" | "male" | "neutral";
  rounds: ExperienceRound[];
};

/**
 * Settle the email question for a Google account, whichever way they answered.
 *
 * `email_asked_at` is written in the same statement as the address, never after
 * and never separately, so the two cannot drift: an address in this table is an
 * address someone was asked for. A decline passes `null` and gets the timestamp
 * without the address, which is what stops the panel coming back forever.
 *
 * `where email_asked_at is null` rather than a plain assignment, so this is
 * idempotent: a second click, or a decline arriving after an accept, cannot
 * move the timestamp or clear an address that is already there.
 *
 * The one caller is app/api/signups/email, which is the one place that asks.
 *
 * Returns nothing. Nothing on the site reads an address back out.
 */
export async function settleEmailAsk(sub: string, email: string | null): Promise<void> {
  const sql = db();
  await sql`
    update signups set email = ${email}, email_asked_at = now()
    where google_sub = ${sub} and email_asked_at is null
  `;
}

/**
 * Whether this account has been asked about their address yet.
 *
 * Phrased on `email_asked_at` rather than on `email is null` on purpose: this
 * answer reaches a page, and a query that mentions the email column is the one
 * thing tests/email-is-write-only.test.ts exists to stop. A timestamp says
 * everything the page needs and nothing about the person. It is also the right
 * question: someone who said no has been asked, and must not be asked again.
 *
 * True for everyone who joined before there was a column to put an address in,
 * which is most of the wall. They are asked once, on /join.
 */
export async function needsEmailConsent(sub: string): Promise<boolean> {
  const sql = db();
  const rows = (await sql`
    select email_asked_at from signups where google_sub = ${sub} limit 1
  `) as { email_asked_at: string | null }[];
  // No row at all is not "needs asking": they have no profile yet, so they are
  // going through the form, which does the asking itself.
  if (rows.length === 0) return false;
  return rows[0].email_asked_at === null;
}

/**
 * The row a Google account owns, or null if they signed in but never finished
 * their profile. Signing in and being on the wall are two different things:
 * the first is Google's answer, the second is a row here.
 */
export async function signupForGoogleSub(sub: string): Promise<SignupRow | null> {
  const sql = db();
  const rows = (await sql`
    select id, name, country, gender, seed, created_at
    from signups where google_sub = ${sub} limit 1
  `) as SignupRow[];
  return rows[0] ?? null;
}

/**
 * Newest first, optionally filtered by company (case-insensitive prefix
 * match) or by the person who posted them. Rounds come back nested via
 * json_agg so this is one round trip instead of N+1.
 */
export async function recentExperiences({
  company,
  signupId,
  limit = 100,
}: {
  company?: string;
  signupId?: string;
  limit?: number;
}): Promise<ExperienceRow[]> {
  const sql = db();
  const rows = await sql`
    select
      e.id, e.company, e.role, e.result, e.summary, e.created_at,
      e.signup_id, s.name, s.seed, s.gender,
      coalesce(
        (
          select json_agg(
            json_build_object(
              'round_number', r.round_number,
              'round_type', r.round_type,
              'description', r.description,
              'outcome', r.outcome
            ) order by r.round_number
          )
          from experience_rounds r
          where r.experience_id = e.id
        ),
        '[]'
      ) as rounds
    from experiences e
    join signups s on s.id = e.signup_id
    where e.hidden = false
      and (${company ?? null}::text is null or lower(e.company) like lower(${company ?? ""}) || '%')
      and (${signupId ?? null}::bigint is null or e.signup_id = ${signupId ?? null}::bigint)
    order by e.created_at desc
    limit ${limit}
  `;
  return rows as ExperienceRow[];
}

export async function updateSignup(sub: string, name: string, country: string, gender: string, seed: string): Promise<SignupRow | null> {
  const sql = db();
  const rows = (await sql`
    update signups
    set name = ${name}, country = ${country}, gender = ${gender}, seed = ${seed}
    where google_sub = ${sub}
    returning id, name, country, gender, seed, created_at
  `) as SignupRow[];
  return rows[0] ?? null;
}

export async function updateExperience(
  id: string,
  signupId: string,
  company: string,
  role: string,
  result: string,
  summary: string,
  rounds: { round_number: number; round_type: string; description: string; outcome: string }[]
): Promise<boolean> {
  const sql = db();
  const resultRows = (await sql`
    with updated as (
      update experiences
      set company = ${company}, role = ${role}, result = ${result}, summary = ${summary}
      where id = ${id}::bigint and signup_id = ${signupId}::bigint
      returning id
    ), deleted_rounds as (
      delete from experience_rounds
      where experience_id = (select id from updated)
    ), rounds_inserted as (
      insert into experience_rounds (experience_id, round_number, round_type, description, outcome)
      select (select id from updated), r.round_number, r.round_type, r.description, r.outcome
      from jsonb_to_recordset(${JSON.stringify(rounds)}::jsonb)
        as r(round_number int, round_type text, description text, outcome text)
      where exists (select 1 from updated)
      returning experience_id
    )
    select id from updated
  `) as { id: string }[];
  return resultRows.length > 0;
}

export async function deleteExperience(id: string, signupId: string): Promise<boolean> {
  const sql = db();
  const rows = (await sql`
    delete from experiences
    where id = ${id}::bigint and signup_id = ${signupId}::bigint
    returning id
  `) as { id: string }[];
  return rows.length > 0;
}

