# The landing site

Next.js on Vercel, with Neon Postgres behind the wall and the interview
experience board. Separate from the app in `../`, which runs on your own
machine and has its own database.

```bash
npm install
npm run dev        # http://localhost:3001
npm run verify     # lint, copy check, tests, build. Run before pushing.
```

Copy `.env.example` to `.env.local` and fill it in. Every page renders without
any of it: no database means an empty wall, and no Google credentials means a
sign-in button that cannot be used. Neither takes the site down.

## Setting up Google sign-in

Signing in tells two people apart and gives an address to reach them on. The
email is stored, is never shown on the wall and is never read back out by any
page; the avatar is drawn, not taken from the Google account.

Rows created before the `email` column existed have none, and cannot be given
one retroactively: `google_sub` is opaque and Google offers no lookup from it
to an address. They are filled in the next time that person signs in.

**1. Create the OAuth client**

1. Open the [Google Cloud console](https://console.cloud.google.com/), and
   create a project (or pick an existing one).
2. **APIs and Services → OAuth consent screen**. Choose **External**, fill in
   the app name, your support email and developer email, and save. Under
   **Data access** add the `openid`, `.../auth/userinfo.profile` and
   `.../auth/userinfo.email` scopes, which is what the default sign-in asks
   for. Leave the app in **Testing** while you try it out, and add your own
   Google account under **Audience → Test users**. Publish it when you want
   anyone to be able to sign in.
3. **APIs and Services → Credentials → Create credentials → OAuth client ID**.
   Application type **Web application**.
4. Add these, exactly:

   | Field | Value |
   |---|---|
   | Authorised JavaScript origin | `http://localhost:3001` |
   | Authorised JavaScript origin | `https://your-domain.vercel.app` |
   | Authorised redirect URI | `http://localhost:3001/api/auth/callback/google` |
   | Authorised redirect URI | `https://your-domain.vercel.app/api/auth/callback/google` |

   The redirect URI has to match character for character, including the
   scheme and any trailing path. A mismatch is the `redirect_uri_mismatch`
   error, and it is the only thing that error means.
5. Copy the client ID and client secret.

**2. Set the environment variables**

Locally, in `.env.local`:

```bash
AUTH_GOOGLE_ID=xxxxxxxx.apps.googleusercontent.com
AUTH_GOOGLE_SECRET=your-client-secret
AUTH_SECRET=run-npx-auth-secret-to-generate-one
AUTH_URL=http://localhost:3001
```

Generate `AUTH_SECRET` with:

```bash
npx auth secret
```

In Vercel, set the same three under **Settings → Environment Variables**, for
Production and Preview. **Do not set `AUTH_URL` on Vercel** - it works that out
from the request, and a hardcoded one breaks preview deployments.

**3. Apply the database change**

```bash
npm run db:init
```

Idempotent, and additive: it adds a `google_sub` column and its unique index
and touches nothing that is already there.

## How joining works

Three states, all handled by `/join`:

| State | What you see |
|---|---|
| Signed out | A "continue with Google" button |
| Signed in, no profile | Name (prefilled from Google, editable), country, avatar |
| Signed in with a profile | Redirected to the wall |

Only the third can post an interview experience. `lib/viewer.ts` is the one
place that answers "which of these is this request", and both API routes take
the poster's identity from the session cookie rather than from the request
body, so the browser chooses its display name and its face but never whose row
it is writing.

## Migrating a row created before sign-in existed

Rows from before this have `google_sub = null`, so signing in offers a fresh
profile rather than finding the old one. If you want to keep an existing row
and the experiences attached to it, claim it once:

1. Sign in.
2. Open `/api/auth/session` and copy `user.id`. That is your Google `sub`.
3. In the Neon SQL editor:

   ```sql
   update signups set google_sub = 'THE-SUB-YOU-COPIED' where id = THE-ROW-ID;
   ```

Then `/join` finds that row and sends you to the wall.
