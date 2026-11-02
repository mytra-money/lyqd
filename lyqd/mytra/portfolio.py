"""
Mytra-backed portfolio for LYQD.

Positions and transaction history are owned by Mytra. Soft launch returns empty
Mytra payloads plus local instruction rows so the SPA can show the intended
layout and Mytra refs as they land.
"""

from __future__ import annotations

import frappe
from frappe.utils import flt


def fetch_mytra_positions(company: str) -> list[dict]:
	"""
	Positions mirrored from Mytra for this company.

	Wire to Mytra HTTP when the investment account link is live.
	"""
	_ = company
	return []


def fetch_mytra_transactions(company: str) -> list[dict]:
	"""
	Purchase / redemption history from Mytra for this company.

	Wire to Mytra HTTP when the investment account link is live.
	"""
	_ = company
	return []


def get_portfolio(company: str) -> dict:
	"""SPA portfolio: Mytra positions + history, with local instruction trail."""
	company = company or ""
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

	return {
		"company": company,
		"positions": positions,
		"transactions": history,
		"liquid_total": liquid_total,
		"mytra_sync": False,
		"message": (
			"Holdings balances and full transaction history sync from Mytra once the "
			"investment account is linked. Local instructions appear below until then."
			if not positions and not mytra_txns
			else None
		),
	}
