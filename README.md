<div align="center" markdown="1">

<img src="lyqd/public/images/lyqd.svg" alt="LYQD logo" width="80" />
<h1>LYQD</h1>

**Know what cash you can invest — and when you’ll need it.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](license.txt)

</div>

## LYQD

LYQD helps finance teams forecast upcoming payments, identify potential surplus cash, and manage mutual fund investment workflows with clear approvals and transaction tracking. It runs on [Frappe](https://github.com/frappe/frappe); [ERPNext](https://github.com/frappe/erpnext) is an **optional** books source (this site or other site), same pattern as Frappe CRM.

Bank statement balances, near-term commitments, and a liquidity policy feed one explainable free-cash number. From there you can open an investment request, issue an instruction, and track liquid holdings — without maintaining a second ledger outside the books.

Product overview: [mytra.money/lyqd](https://mytra.money/lyqd).

### Why this exists

Service businesses (IT, SaaS, consulting, BPO, professional services) often collect fees and retainers ahead of payroll, vendor bills, and taxes. Large balances then sit in current accounts because the next payment date feels unclear — teams fear a shortfall more than they value idle float.

Typical gaps:

1. **Large current-account balances** — Collections land before salaries, vendors, GST/TDS, and rent are due.
2. **Unclear “safe to invest”** — Without a forecast, surplus stays idle.
3. **Scattered approvals** — Spreadsheets and ad-hoc email make decisions hard to review later.
4. **Hard to plan redemptions** — Without visible holdings and status, redeeming ahead of a due date feels risky.

LYQD closes that loop on ERPNext: cash position, commitments, free cash, invest, and portfolio share one company context and one formula.

### Why liquid mutual funds?

Idle current-account cash typically earns little or nothing between known payment dates. Very short bank deposits, when available, are a different product from mutual funds and often carry lower illustrative rates than longer tenors.

LYQD’s initial scheme focus is a **liquid mutual fund** because that category is commonly considered for **short-term surplus** — money that may be needed again for payroll, taxes, or vendors within days or weeks. Product-fit rationale (not a performance guarantee):

- **Fits the payment calendar** — Parking cash between known obligation dates, not multi-year investing.
- **Plan redemptions ahead** — Schedule redemption before a due date, subject to scheme cut-offs, business days, and settlement.
- **Vs idle operating cash** — Operating balances are for day-to-day needs; invested surplus is what remains after dues and a buffer.
- **What it is not** — Not a bank deposit, not a substitute for operating cash, and not a promise of fixed returns or same-day bank credit.

Human approval before investment instructions — no autonomous trading. Mutual fund investments are subject to market risks; read all scheme-related documents carefully.

### The treasury app

A Vue 3 + [Frappe UI](https://github.com/frappe/frappe-ui) app served at `/lyqd`, and registered on the desk apps screen next to ERPNext.

- **Cash position** — Bank statement balances, portfolio snapshot, commitments in the horizon, free cash, and alerts when redemption may be needed.
- **Commitments** — Planned payments that reserve cash (including overdue). Optional “from books” suggestions can be accepted onto the plan with a due date.
- **Free cash** — Explainable waterfall: bank cash − planned commitments − buffer − restricted cash.
- **Invest** — One open investment request per company; confirm amount, then create an instruction once the investment account is activated.
- **Portfolio** — Holding balances and transaction history from Mytra (instructions link via Mytra transaction ref).

```
Cash position  →  Commitments  →  Free cash  →  Invest  →  Portfolio
```

### Free cash

```
free_cash =
  sum(LYQD Bank Balance for eligible LYQD Bank Accounts)
  − sum(Planned commitments due on or before today + horizon)
  − min_liquidity_buffer
  − restricted_cash
```

Overdue Planned commitments are included. Cash masters are **LYQD Company**, **LYQD Bank Account**, and **LYQD Bank Balance** — no Chart of Accounts dependency.

### LYQD Company (one record per cash entity)

**LYQD Company** is the SaaS cash-management entity. Desk form uses tabs:

| Tab | Contents |
|-----|----------|
| **Details** | Name, abbr, currency, active, notes |
| **Books** | Manual / This Site / Other Site; remote URL + API key & secret; books company name |
| **Policy** | Liquidity buffer, restricted cash, forecast horizon, eligible bank accounts |
| **Recommendations** | From-books account list (Data names that must match the books COA when connected) |
| **Investment** | Ops-owned activation stamp (SPA cannot toggle) |

Multi-company on one site is supported: each company has its own books connector and investment activation. Site-wide defaults (horizon / buffers when a company is new) live on **LYQD Settings**.

### ERPNext integration (optional)

Same idea as Frappe CRM: LYQD installs without ERPNext. Books are opt-in **per LYQD Company** (Books tab / SPA Settings → Integrations):

- **This site** — local ERPNext must be installed; Payment Ledger + GL recommendations.
- **Other site** — remote ERPNext via URL + API key & secret (read-only). Banks are mirrored into **LYQD Bank Account**; balances stay on this site.
- **Manual** — enter statement balances in LYQD with no books connector.

**Sync plan from books** updates Accepted rows from voucher outstanding or GL balances. Purchase Receipt suggestions exclude receipts that already have a Purchase Invoice.

Asset accounts (for example Input GST) can be added as **Setoff** so they reduce net commitments when paired with Output GST liabilities.

### Investment account

Instructions require an activated investment account **on that LYQD Company**. Activation is **ops-owned** (Desk / internal site) — the SPA only shows status when active; otherwise **Request activation** opens the Mytra WhatsApp chatbot (CRM Lead is created by the bot, not the SPA).

Schemes and holdings come from **Mytra**. A Ready instruction is submitted to Mytra (creates a transaction); `mytra_transaction_ref` is used to track status and to show the same activity under Portfolio → transaction history. Position cards sync from Mytra balances — there is no manual “Add holding” in the SPA.

**Soft-launch Portfolio demo** — while Mytra HTTP is not wired, `lyqd.mytra.portfolio` can return SAMPLE positions/transactions when any active LYQD Company has **Investment Account Activated** (or `lyqd_demo_portfolio` site config is `1`). Disable with:

```bash
bench --site <site> set-config lyqd_demo_portfolio 0
```

Optional instruction bridge rows (matching sample Mytra refs):

```bash
bench --site <site> execute lyqd.setup.seed_portfolio_demo.seed_portfolio_demo --kwargs "{'company': '<LYQD Company>'}"
```

### Key features

- **Explainable free cash** — Same formula on Cash position and Free cash, with horizon control.
- **Company policy** — Eligible banks, liquidity buffer, restricted cash, and recommendation accounts on the company itself.
- **Commitments plan** — Manual payments plus accept-from-books; Outflow vs Setoff cash effects.
- **Investment workflow** — Draft → confirmed request → instruction (approve / ready).
- **Session caching** — Cash position and Commitments keep recent data across navigation; Refresh forces a reload. Book sync is explicit, not on every page open.

### Under the hood

- [Frappe Framework](https://github.com/frappe/frappe) — Full-stack Python web framework.
- [ERPNext](https://github.com/frappe/erpnext) — Optional books (This Site / Other Site).
- [Frappe UI](https://github.com/frappe/frappe-ui) — Vue 3 component library for the SPA.

## Install

On a Frappe bench (ERPNext optional):

```bash
cd frappe-bench
bench get-app https://github.com/mytra-money/lyqd.git
bench --site <site> install-app lyqd
bench --site <site> migrate
```

### Frontend build (required)

The Vue SPA is **not** committed. Build it after install or whenever you change `frontend/`:

```bash
cd apps/lyqd/frontend && yarn && yarn build
bench --site <site> clear-cache
```

This writes assets to `lyqd/public/frontend/` and `lyqd/www/lyqd.html` (both gitignored).

### Demo data (optional)

```bash
bench --site <site> execute lyqd.setup.seed.seed_demo
```

## Roles

| Role | Access |
|------|--------|
| LYQD User | Commitments, free cash, view invest and portfolio |
| LYQD Manager | Company (policy / books), banks, confirm invest |
| System Manager | All |

## Tests

```bash
bench --site <site> run-tests --app lyqd --module lyqd.cash.test_surplus
```

## About Mytra

LYQD is developed by [Mytra](https://mytra.money) for corporate liquidity on ERPNext. Learn more on the product page: [mytra.money/lyqd](https://mytra.money/lyqd).

---

<div align="center">

Make idle cash work smarter.

</div>
