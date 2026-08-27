-- The whole database for the wall. Paste this into the Neon SQL editor once.
--
-- No migration tool, deliberately. One table, of names, that will not change
-- shape. Alembic exists in this project for the app's own schema, which is a
-- different database on a different machine.
--
-- There is no raw IP in here, only a salted hash of one.
--
-- There is an email column, added later than the rest. It is the one field in
-- this database that would matter if it leaked, so it is written but never
-- read back out: no query that feeds a page selects it, and it is deliberately
-- absent from the SignupRow type, because that type is serialised into the
-- HTML every visitor receives.
--
-- An address is only ever written next to an `email_asked_at`, so "when did we
-- get this" is answerable from the row rather than from memory of which deploy
-- was live on the day.

create table if not exists signups (
  id         bigint generated always as identity primary key,
  name       text        not null check (length(name) between 1 and 24),
  country    char(2)     not null,
  gender     text        not null check (gender in ('female','male','neutral')),
  seed       text        not null check (length(seed) <= 64),
  -- sha256(ip + SIGNUP_IP_SALT). Rate limiting works the same on a hash, and
  -- then there is no address in here to lose.
  ip_hash    text        not null,
  -- A uuid the browser keeps in localStorage. Superseded by google_sub below,
  -- and kept only so rows created before sign-in existed still resolve.
  client_id  text,
  created_at timestamptz not null default now()
);

-- Google's `sub` for the account that owns this row: stable, opaque, and not
-- an email address. This is the whole of what signing in adds to the database,
-- which is why there is no adapter and no users/accounts/sessions tables.
alter table signups add column if not exists google_sub text;

-- The email on the Google account, so there is a way to reach people about the
-- thing they signed up for.
--
-- Nullable, and null for everyone who joined before this column existed. Their
-- address was never stored and cannot be recovered from the row: `google_sub`
-- is opaque and Google offers no lookup from it back to an address. Those rows
-- fill in the next time that person signs in, which is why the session epoch in
-- auth.ts was bumped: it sends everyone back through Google once.
alter table signups add column if not exists email text;

-- When the address in the column beside this one was recorded.
--
-- Written in the same statement as the address itself, never separately, by
-- both of the two writes: the insert in app/api/signups when someone fills in
-- the profile form, and `saveEmail` on every sign-in after that. So an address
-- with no `email_asked_at` beside it is a bug rather than a state, and the
-- states read cleanly:
--
--   email_asked_at is null, email null     joined before the column existed
--   email_asked_at set, email set          recorded, at that time
--
-- The name is older than the current behaviour. It was the timestamp on a
-- consent panel that /join used to show, back when the address was asked for
-- rather than taken with the sign-in. Renaming it means a migration on a live
-- table for no behaviour, so it stays.
alter table signups add column if not exists email_asked_at timestamptz;

-- The board read.
create index if not exists signups_created_at_idx on signups (created_at desc);

-- The rate limit lookup, which runs inside the insert.
create index if not exists signups_ip_hash_created_at_idx on signups (ip_hash, created_at desc);

-- One row per browser. Partial, so the many null client_ids do not collide.
create unique index if not exists signups_client_id_key
  on signups (client_id) where client_id is not null;

-- One row per Google account, for the same reason and in the same shape.
create unique index if not exists signups_google_sub_key
  on signups (google_sub) where google_sub is not null;

-- Coffees. Someone liked this enough to cover a bit of the hosting bill.
--
-- Every row is a payment Razorpay confirmed, never one the browser claimed
-- happened: the insert runs after a signature check on the server, and the
-- webhook writes the same row if the browser closed before it could.
--
-- `signup_id` is what earns the ring on the wall, and it is nullable because
-- paying does not require signing in. Someone who paid signed out carries a
-- claim token in their own browser and can attach the coffee to their row
-- after they join.
create table if not exists coffees (
  id                  bigint generated always as identity primary key,
  signup_id           bigint references signups (id) on delete set null,
  -- What the card was charged, in paise. Always INR: the page is priced in the
  -- reader's own currency and settled in rupees. See lib/currency.ts.
  amount_paise        int         not null check (amount_paise > 0),
  -- What the page showed them, so a question about a payment can be answered
  -- in the numbers they actually saw rather than in the ones we charged.
  display_currency    char(3)     not null,
  display_amount      numeric(12, 2) not null,
  razorpay_order_id   text        not null,
  razorpay_payment_id text        not null,
  -- Handed to the browser once, on success, and kept in its localStorage. It
  -- is the only way back to an unclaimed row, and it is cleared the moment it
  -- is used.
  claim_token         text,
  created_at          timestamptz not null default now()
);

-- The webhook and the browser both try to write the same payment, and whichever
-- arrives second must not create a duplicate. This is what makes the insert
-- idempotent rather than a race.
create unique index if not exists coffees_payment_id_key
  on coffees (razorpay_payment_id);

-- The supporter lookup that every wall render runs.
create index if not exists coffees_signup_id_idx
  on coffees (signup_id) where signup_id is not null;

-- Claiming, which is a lookup by token on a row that has no owner yet.
create unique index if not exists coffees_claim_token_key
  on coffees (claim_token) where claim_token is not null;
