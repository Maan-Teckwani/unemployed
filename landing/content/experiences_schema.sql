-- The interview/OA experience wall. Paste this into the Neon SQL editor once,
-- same as content/schema.sql. A separate file because it's a separate feature
-- that should roll out (and roll back) independently of the signup wall.
--
-- No migration tool here either. Posting requires an existing signup row, so
-- there is no password anywhere in this database and nothing on an experience
-- identifies its author beyond the name and avatar they already put on the
-- wall. Addresses live in signups.email and are covered by the note there;
-- nothing in this file reads one.

create table if not exists experiences (
  id         bigint generated always as identity primary key,
  signup_id  bigint      not null references signups (id),
  company    text        not null check (length(company) between 1 and 80),
  role       text        not null check (length(role) between 1 and 80),
  result     text        not null check (result in ('offer', 'rejected', 'withdrawn', 'pending')),
  summary    text         not null check (length(summary) between 1 and 2000),
  -- sha256(ip + SIGNUP_IP_SALT), same rate-limit trick as signups.
  ip_hash    text        not null,
  flag_count int         not null default 0,
  hidden     boolean     not null default false,
  created_at timestamptz not null default now()
);

-- Round-by-round breakdown. A fixed shape (type + outcome + description), not
-- freeform JSON, because filtering "every OA round at this company" only
-- works cheaply over real columns.
create table if not exists experience_rounds (
  id             bigint generated always as identity primary key,
  experience_id  bigint not null references experiences (id) on delete cascade,
  round_number   int    not null check (round_number between 1 and 20),
  round_type     text   not null check (round_type in (
                   'oa', 'technical', 'system_design', 'hr', 'managerial',
                   'group_discussion', 'other'
                 )),
  description    text   not null check (length(description) between 1 and 1000),
  outcome        text   not null check (outcome in ('cleared', 'rejected', 'pending')),
  unique (experience_id, round_number)
);

-- One flag per browser per experience. Reaching the threshold hides the post;
-- there is no admin UI, unhiding is a manual update in the Neon SQL console.
create table if not exists experience_flags (
  id             bigint generated always as identity primary key,
  experience_id  bigint      not null references experiences (id) on delete cascade,
  ip_hash        text        not null,
  created_at     timestamptz not null default now(),
  unique (experience_id, ip_hash)
);

-- The company filter and the board read.
create index if not exists experiences_company_idx
  on experiences (lower(company), created_at desc) where hidden = false;
create index if not exists experiences_created_at_idx
  on experiences (created_at desc) where hidden = false;

-- Rounds for one experience, in order.
create index if not exists experience_rounds_experience_id_idx
  on experience_rounds (experience_id);

-- The rate limit lookup, same shape as signups_ip_hash_created_at_idx.
create index if not exists experiences_ip_hash_created_at_idx
  on experiences (ip_hash, created_at desc);
