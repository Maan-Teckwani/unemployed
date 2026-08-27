# Buy me a coffee

A tip jar at `/coffee` on the landing site, paid through Razorpay.

Written down here rather than in `landing/.env.example`, because that file is
covered by the `.env*` rule in `landing/.gitignore` and never reaches the repo.

## What it does

- Draws a mug that fills to the amount picked. Full cup at the top preset.
- Prices in the reader's own currency, from the Vercel geo header, and charges
  in rupees. Both numbers are on the page before the button is pressed.
- Puts a ring on the payer's face on the wall, a third tier below maker and
  contributor, and pins them to the front of it.

## Switching it on

### 1. The table

One new table, `coffees`, appended to `landing/content/schema.sql`. Every
statement is `if not exists`, so this is safe to run against a database that
already has the wall in it:

```bash
cd landing && npm run db:init
```

Until this runs, the wall logs `relation "coffees" does not exist` and renders
with nobody marked, which is the intended degradation rather than a failure.

### 2. Razorpay keys

Dashboard, Account & Settings, API Keys. Add the new website to the account
first (Account & Settings, Business Details), since the keys are shared with
the other product on it and the review is per website.

```
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxx
RAZORPAY_KEY_SECRET=
```

Without both, `/coffee` renders with the button disabled and says out loud that
payments are not switched on. Nothing 500s.

### 3. The webhook

Dashboard, Account & Settings, Webhooks. Point it at
`https://your-domain/api/coffee/webhook`, subscribe to `payment.captured`, and
put the secret you choose there in:

```
RAZORPAY_WEBHOOK_SECRET=
```

This is the safety net for somebody who pays and closes the tab before the
browser reports back. Every delivery is rejected while the variable is unset,
which is deliberate: an unauthenticated endpoint that writes rows is worse than
one that is switched off.

## International payments

Checked against Razorpay's own documentation, August 2026.

Razorpay **can** take international payments, but it is not on by default and is
not only a code change:

- The account must have completed KYC and be fully activated on domestic
  payments first.
- International is then activated per account under Account & Settings, and
  first-time enablement goes through Razorpay support and the banking partner.
- The website is reviewed. Clearly defined pages are part of what they check,
  which is what `/legal` exists for.
- 160+ presentment currencies are supported. **Settlement is always INR** into
  the Indian bank account, whatever the payer was charged in.
- Fees: roughly 2% + 18% GST domestic, up to 3% + 18% GST on international
  cards.

### What this build does about it

It charges everyone in INR and shows foreign readers a rounded amount in their
own currency, saying plainly what the card will be charged. That needs no
international activation and is the cheaper rate.

Charging natively in a foreign currency is one field: `currency` in the order
body in `landing/app/api/coffee/order/route.ts`, and the matching field in the
checkout options in `landing/components/coffee/coffee-form.tsx`. The ladders in
`landing/lib/currency.ts` already carry a real per-currency price, so switching
over is changing `"INR"` to `currency.code` in those two places and deleting the
`charged` sentence from the copy. Do not do it before Razorpay has approved the
website for international, or every foreign payment fails at the gateway.

## Sources

- https://razorpay.com/docs/payments/international-payments/
- https://razorpay.com/docs/payments/international-payments/international-debit-credit-cards/
- https://razorpay.com/pricing/
