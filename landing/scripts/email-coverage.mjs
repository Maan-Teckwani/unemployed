/**
 * How far the email recovery has got, in three numbers.
 *
 * Everyone on the wall before there was an email column has no address on their
 * row. Bumping SESSION_EPOCH in auth.ts signs them all out, and signing back in
 * records it. This is how you watch that happen without guessing.
 *
 * Deliberately a script and not a function in lib/db.ts. Anything in there is
 * one import away from a page, and tests/email-is-write-only.test.ts exists to
 * stop a `select` on that column ever getting close to one. Counts are safe
 * because a count is not an address, but the safety comes from this file being
 * somewhere a page cannot reach, not from the query being aggregate.
 *
 *   npm run email:coverage
 */
import { neon } from "@neondatabase/serverless";

const url = process.env.DATABASE_URL;
if (!url) {
  console.error("DATABASE_URL is not set. Copy .env.example to .env.local first.");
  process.exit(1);
}

const sql = neon(url);

const [row] = await sql`
  select
    count(*)::int                                              as total,
    -- Seed rows are not people, so they are left out of both of these: they
    -- have no address and never will, and counting them as work left to do
    -- would make the percentages lie.
    count(*) filter (
      where email is not null and ip_hash <> 'seed-demo'
    )::int                                                     as kept,
    count(*) filter (
      where email is null and ip_hash <> 'seed-demo'
    )::int                                                     as missing,
    -- The invariant: an address is only ever written beside a timestamp. This
    -- should be zero forever. If it is not, something wrote a column directly.
    count(*) filter (
      where email is not null and email_asked_at is null
    )::int                                                     as orphaned,
    -- Reported separately, so the headcount above the percentages is people.
    count(*) filter (where ip_hash = 'seed-demo')::int         as demo
  from signups
`;

const real = row.total - row.demo;
const pct = (n) => (real === 0 ? "0.0" : ((n / real) * 100).toFixed(1));

console.log(`on the wall        ${real}${row.demo > 0 ? `  (+${row.demo} demo rows)` : ""}`);
console.log(`address kept       ${row.kept}  (${pct(row.kept)}%)`);
console.log(`no address yet     ${row.missing}  (${pct(row.missing)}%)`);

if (row.orphaned > 0) {
  console.warn(`\nwarning: ${row.orphaned} row(s) hold an address with no timestamp beside it.`);
  console.warn("Nothing in the app can produce that. Find what wrote them.");
  process.exitCode = 1;
}
