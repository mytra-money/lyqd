"""
Mytra-backed portfolio for LYQD.

Positions and transaction history are owned by Mytra. Soft launch can serve
clearly marked SAMPLE payloads so Portfolio looks populated before HTTP sync.

Disable sample data
-------------------
- Site config: ``bench --site <site> set-config lyqd_demo_portfolio 0``
  (forces off even if the investment account is activated)
- Or leave ``lyqd_demo_portfolio`` unset and turn off
  **Investment Account Activated** on LYQD Settings (ops Desk).
- Force on without activation: ``set-config lyqd_demo_portfolio 1``

Real Mytra HTTP is not wired here — replace ``_SAMPLE_*`` when the link is live.
"""

from __future__ import annotations

import frappe
from frappe.utils import flt


# Soft-launch SAMPLE shapes — match Holdings.vue / get_portfolio merge keys.
_SAMPLE_SCHEME = "ICICI Prudential Liquid Fund - Direct Growth"
_SAMPLE_ISIN = "INF109K01VQ1"
_SAMPLE_SCHEME_2 = "HDFC Liquid Fund - Direct Growth"
_SAMPLE_ISIN_2 = "INF179KB1HQ6"

_SAMPLE_POSITIONS = [
	{
		"scheme_label": _SAMPLE_SCHEME,
		"scheme": _SAMPLE_SCHEME,
		"scheme_isin": _SAMPLE_ISIN,
		"amount": 1_250_000.0,
		"units": 4123.4567,
		"nav": 303.12,
		"as_on": "2026-11-02",
		"mytra_position_ref": "POS-SAMPLE-001",
		"_sample": True,
	},
	{
		"scheme_label": _SAMPLE_SCHEME_2,
		"scheme": _SAMPLE_SCHEME_2,
		"scheme_isin": _SAMPLE_ISIN_2,
		"amount": 380_000.0,
		"units": 945.2100,
		"nav": 401.99,
		"as_on": "2026-11-02",
		"mytra_position_ref": "POS-SAMPLE-002",
		"_sample": True,
	},
]

_SAMPLE_TRANSACTIONS = [
	{
		"source": "mytra",
		"kind": "Purchase",
		"status": "Allotted",
		"scheme_label": _SAMPLE_SCHEME,
		"scheme_isin": _SAMPLE_ISIN,
		"amount": 500_000.0,
		"mytra_transaction_ref": "UT-SSA-00042",
		"as_of": "2026-10-28",
		"modified": "2026-10-28 14:22:00",
		"_sample": True,
	},
	{
		"source": "mytra",
		"kind": "Redemption",
		"status": "Allotted",
		"scheme_label": _SAMPLE_SCHEME,
		"scheme_isin": _SAMPLE_ISIN,
		"amount": 150_000.0,
		"mytra_transaction_ref": "UT-SSA-00051",
		"as_of": "2026-10-30",
		"modified": "2026-10-30 11:05:00",
		"_sample": True,
	},
	{
		"source": "mytra",
		"kind": "Purchase",
		"status": "Order Placed",
		"scheme_label": _SAMPLE_SCHEME_2,
		"scheme_isin": _SAMPLE_ISIN_2,
		"amount": 200_000.0,
		"mytra_transaction_ref": "UT-SSA-00058",
		"as_of": "2026-11-01",
		"modified": "2026-11-01 16:40:00",
		"_sample": True,
	},
]


def use_demo_portfolio() -> bool:
	"""
	Whether to return SAMPLE Mytra positions/transactions.

	``lyqd_demo_portfolio`` site_config:
	- ``1`` / ``true`` → always on
	- ``0`` / ``false`` → always off
	- unset → on only when Investment Account Activated (soft-launch default)
	"""
	flag = frappe.conf.get("lyqd_demo_portfolio")
	if flag is not None and flag != "":
		if isinstance(flag, str):
			return flag.strip().lower() in ("1", "true", "yes", "on")
		return bool(flag)
	if not frappe.db.exists("DocType", "LYQD Settings"):
		return False
	return bool(frappe.db.get_single_value("LYQD Settings", "investment_account_activated"))


def fetch_mytra_positions(company: str) -> list[dict]:
	"""
	Positions mirrored from Mytra for this company.

	SAMPLE when ``use_demo_portfolio()``; otherwise empty until HTTP is wired.
	"""
	_ = company
	if use_demo_portfolio():
		return [dict(row) for row in _SAMPLE_POSITIONS]
	return []


def fetch_mytra_transactions(company: str) -> list[dict]:
	"""
	Purchase / redemption history from Mytra for this company.

	SAMPLE when ``use_demo_portfolio()``; otherwise empty until HTTP is wired.
	"""
	_ = company
	if use_demo_portfolio():
		return [dict(row) for row in _SAMPLE_TRANSACTIONS]
	return []


def get_portfolio(company: str) -> dict:
	"""SPA portfolio: Mytra positions + history, with local instruction trail."""
	company = company or ""
	demo = use_demo_portfolio()
	positions = fetch_mytra_positions(company)
	mytra_txns = fetch_mytra_transactions(company)

	instructions = frappe.get_all(
		"LYQD Investment Instruction",
		filters={"company": company, "status": ("!=", "Cancelled")},
		fields=[
			"name",
			"status",
			"amount",
			"scheme_label",
			"scheme_isin",
			"as_of",
			"external_submit_status",
			"mytra_transaction_ref",
			"modified",
			"creation",
		],
		order_by="modified desc",
		limit=50,
	)

	# Bridge: local instructions awaiting / linked to Mytra appear in history.
	local_history = []
	for row in instructions:
		local_history.append(
			{
				"source": "lyqd",
				"name": row.name,
				"kind": "Purchase instruction",
				"scheme_label": row.scheme_label,
				"scheme_isin": row.scheme_isin,
				"amount": flt(row.amount),
				"status": row.status,
				"external_submit_status": row.external_submit_status,
				"mytra_transaction_ref": row.mytra_transaction_ref,
				"as_of": row.as_of,
				"modified": row.modified,
			}
		)

	history = list(mytra_txns) + local_history
	liquid_total = flt(sum(flt(p.get("amount") or 0) for p in positions))
	has_mytra = bool(positions or mytra_txns)

	message = None
	if demo and has_mytra:
		message = (
			"Sample Mytra portfolio for soft-launch demo. "
			"Turn off with: bench --site <site> set-config lyqd_demo_portfolio 0"
		)
	elif not has_mytra:
		message = (
			"Holdings balances and full transaction history sync from Mytra once the "
			"investment account is linked. Local instructions appear below until then."
		)

	return {
		"company": company,
		"positions": positions,
		"transactions": history,
		"liquid_total": liquid_total,
		"mytra_sync": bool(demo and has_mytra),
		"demo": demo,
		"message": message,
	}
