"""Company bank accounts + statement balances from the configured Other Site."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import flt, getdate, today

from lyqd.recommendations.remote import get_remote_client


def remote_has_doctype(client, doctype: str) -> bool:
	"""True if the remote site exposes this DocType to the API key."""
	try:
		client.get_list(doctype, fields=["name"], limit_page_length=1)
		return True
	except Exception as e:
		msg = str(e).lower()
		# Explicit missing DocType / 404
		if "not found" in msg or "does not exist" in msg or "404" in msg:
			return False
		try:
			rows = client.get_list(
				"DocType",
				filters={"name": doctype},
				fields=["name"],
				limit_page_length=1,
			)
			return bool(rows)
		except Exception:
			return False


def list_remote_bank_accounts(
	selected: list[str] | None = None, lyqd_company: str | None = None
) -> list[dict[str, Any]]:
	"""Company bank accounts on the remote ERPNext site."""
	client, company = get_remote_client(lyqd_company)
	filters: dict[str, Any] = {
		"company": company,
		"is_company_account": 1,
		"disabled": 0,
	}
	if selected:
		filters["name"] = ["in", selected]

	rows = (
		client.get_list(
			"Bank Account",
			filters=filters,
			fields=[
				"name",
				"account_name",
				"account",
				"bank",
				"is_default",
				"account_type",
				"account_subtype",
				"bank_account_no",
				"last_integration_date",
				"company",
			],
			order_by="is_default desc, account_name asc",
			limit_page_length=200,
		)
		or []
	)
	for row in rows:
		row["account_currency"] = None
		row["books_source"] = "Other Site"
		row["books_company"] = company
	return rows


def get_remote_statement_balance(client, bank_account: str, as_of: str | None = None) -> dict[str, Any]:
	"""Latest Bank Account Balance on remote on or before as_of (mirrors Banking closing)."""
	as_of = str(getdate(as_of or today()))
	rows = (
		client.get_list(
			"Bank Account Balance",
			filters={
				"bank_account": bank_account,
				"date": ["<=", as_of],
			},
			fields=["name", "date", "balance"],
			order_by="date desc",
			limit_page_length=1,
		)
		or []
	)
	if not rows:
		return {"balance": 0.0, "balance_date": None, "as_of": as_of, "source": "remote_bab"}
	row = rows[0]
	return {
		"balance": flt(row.get("balance")),
		"balance_date": row.get("date"),
		"as_of": as_of,
		"source": "remote_bab",
	}


# NOTE: LYQD never inserts/updates/deletes on the remote site.
# Balances and plan rows are written only on this site. Remote is read-only.
