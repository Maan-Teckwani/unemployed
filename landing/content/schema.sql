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
-- address was never stored and cannot be recovered: `google_sub` is opaque and
-- Google offers no lookup from it back to an address. The only way those rows
-- ever get filled in is the next time that person signs in, which is what
-- auth.ts does.
alter table signups add column if not exists email text;

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
