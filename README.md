<div align="center" markdown="1">

<img src="lyqd/public/images/lyqd.svg" alt="LYQD logo" width="80" />
<h1>LYQD</h1>

**Know what cash you can invest — and when you’ll need it.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](license.txt)

</div>

## LYQD

LYQD is Mytra’s corporate liquidity app for finance teams: forecast upcoming payments, see explainable free cash, and run **Invest** / **Redeem** proposals through to mutual-fund instructions — with holdings and history in one place.

It runs on [Frappe](https://github.com/frappe/frappe). [ERPNext](https://github.com/frappe/erpnext) is optional and only used when a LYQD Company connects books (this site or another site). Statement balances always stay on the LYQD site.

**Live soft-launch:** [lyqd.mytra.money](https://lyqd.mytra.money) · Product: [mytra.money/lyqd](https://mytra.money/lyqd)

### Why this exists

Service businesses (IT, SaaS, consulting, BPO, professional services) often collect fees and retainers ahead of payroll, vendor bills, and taxes. Large balances then sit in current accounts because the next payment date feels unclear — teams fear a shortfall more than they value idle float.

Typical gaps:

1. **Large current-account balances** — Collections land before salaries, vendors, GST/TDS, and rent are due.
2. **Unclear “safe to invest”** — Without a forecast, surplus stays idle.
3. **Scattered approvals** — Spreadsheets and ad-hoc email make decisions hard to review later.
4. **Hard to plan redemptions** — Without visible holdings and status, redeeming ahead of a due date feels risky.

LYQD closes that loop: cash position, commitments, free cash, proposals (invest / redeem), and portfolio share one company context and one formula.

### Why liquid mutual funds?

Idle current-account cash typically earns little or nothing between known payment dates. Very short bank deposits, when available, are a different product from mutual funds and often carry lower illustrative rates than longer tenors.

LYQD’s initial scheme focus is a **liquid mutual fund** because that category is commonly considered for **short-term surplus** — money that may be needed again for payroll, taxes, or vendors within days or weeks. Product-fit rationale (not a performance guarantee):

- **Fits the payment calendar** — Parking cash between known obligation dates, not multi-year investing.
- **Plan redemptions ahead** — Schedule redemption before a due date, subject to scheme cut-offs, business days, and settlement.
- **Vs idle operating cash** — Operating balances are for day-to-day needs; invested surplus is what remains after dues and a buffer.
- **What it is not** — Not a bank deposit, not a substitute for operating cash, and not a promise of fixed returns or same-day bank credit.

Human approval before investment instructions — no autonomous trading. Mutual fund investments are subject to market risks; read all scheme-related documents carefully.

### Soft launch — lyqd.mytra.money

Hosted beta for early customers:

| | |
|--|--|
| **URL** | [https://lyqd.mytra.money](https://lyqd.mytra.money) |
| **App** | SPA at `/lyqd` after login |
| **Signup** | Public signup enabled; default role **LYQD Manager** (SPA only — no Desk) |
| **Home** | Website home routes to `/lyqd` |
| **Welcome mail** | System Settings → template **LYQD Welcome** (requires a default Email Account) |

Ops notes for the soft launch:

- Investment account activation remains **ops-owned** on each **LYQD Company**.
- Portfolio may show **sample** Mytra positions while live HTTP is not wired — when any active company has investment activated, or `lyqd_demo_portfolio` is set. Turn off with `bench --site <site> set-config lyqd_demo_portfolio 0`.

### The treasury app

Vue 3 + [Frappe UI](https://github.com/frappe/frappe-ui) SPA at `/lyqd`. Desk registration is for System Managers; day-to-day users work only in the SPA.

**PWA / mobile** — Installable on phone (Add to Home Screen). Manifest: `/api/method/lyqd.api.spa.get_pwa_manifest`. Service worker is emitted by `yarn build` in `frontend/`. Narrow screens use a bottom tab bar + slide-out menu (Cash · Plan · Free · Proposal · More).

- **Cash position** — Local bank statement balances, portfolio snapshot, commitments in the horizon, free cash / shortfall, and proposal drift alerts (e.g. open Invest while the horizon is short → replace with Redeem).
- **Commitments** — Planned payments that reserve cash (including overdue). Optional “from books” suggestions can be accepted onto the plan with a due date.
- **Free cash** — Explainable waterfall: bank cash − planned commitments − buffer − restricted cash.
- **Proposal** (`/lyqd/proposal`) — One open proposal per company: **Invest** when free cash is positive, or **Redeem** when the horizon shows a shortfall (capped by liquid holdings). Based on a saved **Surplus Run**; creates a Purchase or Redeem instruction once the investment account is activated. Starting a new proposal supersedes any prior open one.
- **Portfolio** — Holding balances and transaction history from Mytra (instructions link via Mytra transaction ref).

```
Cash position  →  Commitments  →  Free cash  →  Proposal (Invest / Redeem)  →  Portfolio
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

**Balances are always local.** Free cash and redeem amounts use **LYQD Bank Balance** on this site only. Other Site books may mirror bank *account* masters; statement balances are never pulled from the remote site (update them on `/lyqd/cash`).

### Proposals (Invest & Redeem)

- Creating a proposal always persists (or reuses) a **LYQD Surplus Run** with the free-cash waterfall; the Draft Proposal must link to that run.
- **Invest** — `proposed_amount = free_cash` when free cash is positive; instruction `side = Purchase`.
- **Redeem** — when free cash is a shortfall: `proposed_amount = min(|shortfall|, liquid holdings)`; instruction `side = Redeem`.
- Only one open (Draft / Frozen) proposal per company; a new Invest or Redeem supersedes the prior open proposal.
- If an open **Invest** proposal exists but the selected horizon is a **shortfall**, Cash position prompts to cancel Invest and create a Redeem (not “partially redeem the invest amount”).
- Identical free-cash math reuses the same Surplus Run and open proposal (no duplicate rows).

### Onboarding & multi-company

On first sign-in, if the user has no LYQD Company yet, the SPA opens a **Create company** dialog (company name + optional Manual / This Site / Other Site books). The same dialog is available anytime from the company dropdown (**+ Add company…**).

Non–System Managers receive a **User Permission** on the new LYQD Company so only their companies appear in the nav. System Managers see all companies and do not need a User Permission.

### LYQD Company (one record per cash entity)

**LYQD Company** is the cash-management entity. Desk form (System Manager) uses tabs:

| Tab | Contents |
|-----|----------|
| **Details** | Name, abbr, currency, active, notes |
| **Books** | Manual / This Site / Other Site; remote URL + API key & secret; books company name |
| **Policy** | Liquidity buffer, restricted cash, forecast horizon, eligible bank accounts |
| **Recommendations** | From-books account list (Data names that must match the books COA when connected) |
| **Investment** | Ops-owned activation stamp (SPA cannot toggle) |

Multi-company on one site is supported: each company has its own books connector and investment activation. Site-wide defaults (horizon / buffers when a company is new) live on **LYQD Settings**.

### Books integration (optional)

LYQD does not require ERPNext. Books are opt-in **per LYQD Company** (Books tab / SPA Settings → Integrations):

- **This site** — local ERPNext must be installed; Payment Ledger + GL recommendations.
- **Other site** — remote ERPNext via URL + API key & secret (read-only). Bank *accounts* can be mirrored into **LYQD Bank Account**; **balances always stay on this site** (LYQD Bank Balance).
- **Manual** — enter statement balances in LYQD with no books connector.

**Sync plan from books** updates Accepted rows from voucher outstanding or GL balances. Purchase Receipt suggestions exclude receipts that already have a Purchase Invoice.

Asset accounts (for example Input GST) can be added as **Setoff** so they reduce net commitments when paired with Output GST liabilities.

### Investment account

Instructions require an activated investment account **on that LYQD Company**. Activation is **ops-owned** — the SPA only shows status when active; otherwise **Request activation** opens the Mytra WhatsApp chatbot (lead capture is handled by the bot, not by the SPA).

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

- **Explainable free cash** — Same formula on Cash position and Free cash, with horizon control (7 / 14 / 30 / 60 or custom days).
- **Company policy** — Eligible banks, liquidity buffer, restricted cash, and recommendation accounts on the company itself.
- **Commitments plan** — Manual payments plus accept-from-books; Outflow vs Setoff cash effects.
- **Proposal workflow** — Surplus Run → Invest or Redeem proposal → instruction (Purchase / Redeem; approve / ready).
- **Horizon-aware alerts** — Open proposal vs today’s free cash or shortfall (refresh, cancel, or replace Invest with Redeem).
- **Multi-company onboarding** — Add company from the nav (User Permission for non–System Managers).
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

This writes assets to `lyqd/public/frontend/` and `lyqd/www/lyqd.html` (both gitignored). On Frappe Cloud, root `package.json` `postinstall` / `build` scripts run the same frontend build during deploy.

### Demo data (optional)

```bash
bench --site <site> execute lyqd.setup.seed.seed_demo
```

## Roles

| Role | Access |
|------|--------|
| LYQD User | Commitments, free cash, view proposals and portfolio (SPA only — no Desk) |
| LYQD Manager | Company (policy / books), banks, confirm proposals (SPA only — no Desk); default on public signup |
| System Manager | All (Desk + SPA) |

## Tests

```bash
bench --site <site> run-tests --app lyqd --module lyqd.cash.test_surplus
```

## About Mytra

LYQD is developed by [Mytra](https://mytra.money) for corporate liquidity. Soft launch: [lyqd.mytra.money](https://lyqd.mytra.money). Product page: [mytra.money/lyqd](https://mytra.money/lyqd).

---

<div align="center">

Make idle cash work smarter.

</div>
