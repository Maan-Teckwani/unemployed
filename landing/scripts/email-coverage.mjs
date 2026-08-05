/**
 * How far the email recovery has got, in four numbers.
 *
 * Everyone on the wall before there was an email column joined under copy that
 * said their address was not stored. Rotating AUTH_SECRET signs them all out;
 * signing back in walks them through /join, which asks. This is how you watch
 * that happen without guessing.
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
    count(*) filter (where email_asked_at is null)::int        as never_asked,
    count(*) filter (where email is not null)::int             as kept,
    count(*) filter (
      where email_asked_at is not null and email is null
    )::int                                                     as declined,
    -- The invariant: an address is only ever written beside a timestamp. This
    -- should be zero forever. If it is not, something wrote a column directly.
    count(*) filter (
      where email is not null and email_asked_at is null
    )::int                                                     as orphaned,
    -- Seed rows are not people. They are distinguishable by ip_hash, and
    -- counting them as "never asked" would overstate the work left.
    count(*) filter (where ip_hash = 'seed-demo')::int         as demo
  from signups
`;

const real = row.total - row.demo;
const pct = (n) => (real === 0 ? "0.0" : ((n / real) * 100).toFixed(1));

console.log(`on the wall        ${real}${row.demo > 0 ? `  (+${row.demo} demo rows)` : ""}`);
console.log(`address kept       ${row.kept}  (${pct(row.kept)}%)`);
console.log(`asked, said no     ${row.declined}  (${pct(row.declined)}%)`);
console.log(`never asked        ${row.never_asked}  (${pct(row.never_asked)}%)`);

if (row.orphaned > 0) {
  console.warn(`\nwarning: ${row.orphaned} row(s) hold an address with no record of asking.`);
  console.warn("Nothing in the app can produce that. Find what wrote them.");
  process.exitCode = 1;
}
