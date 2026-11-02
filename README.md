<div align="center" markdown="1">

<img src="lyqd/public/images/lyqd-logo.svg" alt="LYQD logo" width="80" />
<h1>LYQD</h1>

**Corporate liquidity for ERPNext — see free cash, plan commitments, invest the rest**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](license.txt)

</div>

## LYQD

LYQD gives finance teams a morning view of surplus cash on top of ERPNext. Bank statement balances, near-term commitments, and a liquidity policy feed one explainable free-cash number. From there you can open an investment request, issue an instruction, and track liquid holdings — without maintaining a second ledger outside the books.

ERPNext remains the system of record for banks, vouchers, and GL. LYQD reads those masters, keeps a local plan of commitments, and runs the investment workflow in a Vue app at `/lyqd`.

### Motivation

Treasury work on ERPNext usually means exporting balances, juggling spreadsheets for “what is due this week”, and guessing how much is safe to put into liquid funds. Recommendations from payables or tax ledgers live in another report, and nothing ties bank cash, the payment plan, and an investable amount together.

LYQD closes that loop. Cash position, commitments, free cash, invest, and portfolio share one company context and one formula. Optional ERPNext integration pulls liability suggestions from Payment Ledger and GL so the plan stays close to the books — on this site or a connected Other Site (read-only).

### The treasury app

A Vue 3 + [Frappe UI](https://github.com/frappe/frappe-ui) app served at `/lyqd`, and registered on the desk apps screen next to ERPNext.

- **Cash position** — Bank statement balances, portfolio snapshot, commitments in the horizon, free cash, and alerts when redemption may be needed.
- **Commitments** — Planned payments that reserve cash (including overdue). Optional “from books” suggestions can be accepted onto the plan with a due date.
- **Free cash** — Explainable waterfall: bank cash − planned commitments − buffer − restricted cash.
- **Invest** — One open investment request per company; confirm amount, then create an instruction once the investment account is activated.
- **Portfolio** — Liquid fund holdings for the company.

```
Cash position  →  Commitments  →  Free cash  →  Invest  →  Portfolio
```

### Free cash

```
free_cash =
  sum(Bank Account Balance for eligible banks)
  − sum(Planned commitments due on or before today + horizon)
  − min_liquidity_buffer
  − restricted_cash
```

Overdue Planned commitments are included. Statement balances use ERPNext **Bank Account Balance** (same path as Banking closing as per statement).

### ERPNext integration

Integrations are opt-in under Settings.

- **This site** — Liability suggestions from local Payment Ledger (Payable) and GL.
- **Other site** — Remote ERPNext via URL + API key & secret. LYQD only **reads** the remote (liabilities and bank masters), mirrors company bank accounts locally, and stores balances and accepted plan rows on this site. Nothing is written back to the remote.

**Sync plan from books** updates Accepted rows from voucher outstanding or GL balances. Purchase Receipt suggestions exclude receipts that already have a Purchase Invoice.

Asset accounts (for example Input GST) can be added as **Setoff** so they reduce net commitments when paired with Output GST liabilities.

### Investment account

Instructions require an activated investment account (ops-controlled). Until then, users can raise a CRM request to open an account. Further activation fields and instruction acceptance on an internal site are planned separately.

### Key features

- **Explainable free cash** — Same formula on Cash position and Free cash, with horizon control.
- **Company policy** — Eligible banks, liquidity buffer, restricted cash, and recommendation accounts.
- **Commitments plan** — Manual payments plus accept-from-books; Outflow vs Setoff cash effects.
- **Investment workflow** — Draft → confirmed request → instruction (approve / ready).
- **Session caching** — Cash position and Commitments keep recent data across navigation; Refresh forces a reload. Book sync is explicit, not on every page open.

### Under the hood

- [Frappe Framework](https://github.com/frappe/frappe) — Full-stack Python web framework.
- [ERPNext](https://github.com/frappe/erpnext) — Banks, payables, GL, and accounting.
- [Frappe UI](https://github.com/frappe/frappe-ui) — Vue 3 component library for the SPA.

## Install

On an existing bench with ERPNext:

```bash
cd frappe-bench
bench get-app https://github.com/mytra-money/lyqd.git
bench --site <site> install-app lyqd
bench --site <site> migrate
```

### Frontend build

```bash
cd apps/lyqd/frontend && yarn && yarn build
bench --site <site> clear-cache
```

### Demo data (optional)

```bash
bench --site <site> execute lyqd.setup.seed.seed_demo
```

## Roles

| Role | Access |
|------|--------|
| LYQD User | Commitments, free cash, view invest and portfolio |
| LYQD Manager | Policy, banks, confirm invest, schemes |
| System Manager | All |

## Tests

```bash
bench --site <site> run-tests --app lyqd --module lyqd.cash.test_surplus
```

## About Mytra

LYQD is developed by [Mytra](https://mytra.money) for corporate surplus cash on ERPNext.

---

<div align="center">

Make idle cash work smarter.

</div>
