"""Eligible bank cash for LYQD surplus — LYQD Bank Account + LYQD Bank Balance."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import flt, getdate, today


def get_policy_selected_bank_accounts(company: str) -> list[str] | None:
	"""Return selected LYQD Bank Account names from Company Policy tab, or None if all apply."""
	if not company or not frappe.db.exists("LYQD Company", company):
		return None
	selected = frappe.get_all(
		"LYQD Policy Bank Account",
		filters={"parent": company, "parenttype": "LYQD Company"},
		pluck="bank_account",
	)
	return selected or None


def get_company_bank_accounts(
	company: str,
	selected: list[str] | None = None,
) -> list[dict[str, Any]]:
	"""Active LYQD Bank Accounts for a company (optionally filtered by policy)."""
	filters: dict[str, Any] = {
		"company": company,
		"is_active": 1,
	}
	if selected:
		filters["name"] = ("in", selected)

	rows = frappe.get_all(
		"LYQD Bank Account",
		filters=filters,
		fields=[
			"name",
			"account_name",
			"bank",
			"is_default",
			"account_type",
			"bank_account_no",
			"company",
			"currency",
			"books_bank_account",
		],
		order_by="is_default desc, account_name asc",
	)
	books_source = frappe.db.get_value("LYQD Company", company, "books_source") or "Manual"
	books_company = frappe.db.get_value("LYQD Company", company, "books_company") or company
	for row in rows:
		row["account"] = None
		row["account_currency"] = row.get("currency")
		row["books_source"] = books_source
		row["books_company"] = books_company
		row["remote_bank_account"] = row.get("books_bank_account")
	return rows


def get_statement_balance(bank_account: str, as_of: str | None = None) -> dict[str, Any]:
	"""Latest LYQD Bank Balance on or before as_of."""
	as_of = str(getdate(as_of or today()))
	rows = frappe.get_all(
		"LYQD Bank Balance",
		filters={"bank_account": bank_account, "date": ("<=", as_of)},
		fields=["balance", "date"],
		order_by="date desc",
		limit=1,
	)
	if not rows:
		return {"balance": 0.0, "balance_date": None, "as_of": as_of}
	return {
		"balance": flt(rows[0].balance),
		"balance_date": rows[0].date,
		"as_of": as_of,
	}


def get_latest_bank_account_balance(bank_account: str, as_of: str | None = None) -> float | None:
	return flt(get_statement_balance(bank_account, as_of)["balance"])


def set_statement_balance(
	bank_account: str, balance: float, as_of: str | None = None
) -> dict[str, Any]:
	"""Upsert LYQD Bank Balance for a bank account."""
	as_of_d = getdate(as_of or today())
	existing = frappe.db.exists(
		"LYQD Bank Balance", {"bank_account": bank_account, "date": as_of_d}
	)
	company = frappe.db.get_value("LYQD Bank Account", bank_account, "company")
	if existing:
		doc = frappe.get_doc("LYQD Bank Balance", existing)
		doc.balance = flt(balance)
		doc.save(ignore_permissions=True)
		name = doc.name
	else:
		doc = frappe.get_doc(
			{
				"doctype": "LYQD Bank Balance",
				"bank_account": bank_account,
				"company": company,
				"date": as_of_d,
				"balance": flt(balance),
			}
		)
		doc.insert(ignore_permissions=True)
		name = doc.name
	return {
		"bank_account": bank_account,
		"date": str(as_of_d),
		"balance": flt(balance),
		"name": name,
		"source": "lyqd_bank_balance",
	}


# Back-compat alias used by older call sites
set_statement_balance_local_only = set_statement_balance


def resolve_bank_account_cash(
	bank_account_row: dict[str, Any],
	company: str,
	as_of: str | None = None,
) -> dict[str, Any]:
	name = bank_account_row["name"]
	stmt = get_statement_balance(name, as_of)
	return {
		"bank_account": name,
		"name": name,
		"account_name": bank_account_row.get("account_name"),
		"account": bank_account_row.get("account"),
		"gl_account": bank_account_row.get("account"),
		"bank": bank_account_row.get("bank"),
		"is_default": bank_account_row.get("is_default"),
		"account_type": bank_account_row.get("account_type"),
		"bank_account_no": bank_account_row.get("bank_account_no"),
		"balance": flt(stmt["balance"]),
		"balance_date": stmt.get("balance_date"),
		"source": "LYQD Bank Balance",
		"books_source": bank_account_row.get("books_source") or "Manual",
		"books_company": bank_account_row.get("books_company") or company,
		"remote_bank_account": bank_account_row.get("remote_bank_account")
		or bank_account_row.get("books_bank_account"),
	}


def get_eligible_bank_cash(company: str, as_of: str | None = None) -> dict[str, Any]:
	"""Sum eligible company bank cash with per-account explanation rows."""
	from lyqd.recommendations.settings import is_remote_source

	selected = get_policy_selected_bank_accounts(company)
	as_of_s = str(getdate(as_of or today()))
	books_source = frappe.db.get_value("LYQD Company", company, "books_source") or "Manual"
	books_company = frappe.db.get_value("LYQD Company", company, "books_company") or company

	# Keep mirrors fresh when Other Site books are linked
	mirror_info = None
	if is_remote_source(company) or books_source == "Other Site":
		try:
			from lyqd.cash.mirror_banks import mirror_remote_bank_accounts

			mirror_info = mirror_remote_bank_accounts(company)
			books_company = mirror_info.get("books_company") or books_company
		except Exception as e:
			frappe.log_error(title="LYQD remote bank mirror failed")
			return {
				"company": company,
				"books_company": books_company,
				"books_source": "Other Site",
				"as_of": as_of_s,
				"total": 0.0,
				"accounts": [],
				"selection": "policy" if selected else "all_company_accounts",
				"selected_bank_accounts": selected or [],
				"balance_source": "lyqd",
				"message": str(e),
			}

	accounts = get_company_bank_accounts(company, selected=selected)
	rows = []
	total = 0.0
	for ba in accounts:
		row = resolve_bank_account_cash(ba, company, as_of_s)
		rows.append(row)
		total += flt(row["balance"])

	return {
		"company": company,
		"books_company": books_company,
		"books_source": books_source,
		"as_of": as_of_s,
		"total": flt(total),
		"accounts": rows,
		"selection": "policy" if selected else "all_company_accounts",
		"selected_bank_accounts": selected or [],
		"balance_source": "lyqd",
		"message": (mirror_info or {}).get("message") if mirror_info and not accounts else None,
		"mirrored": (
			{"created": mirror_info.get("created"), "updated": mirror_info.get("updated")}
			if mirror_info
			else None
		),
	}


def create_company_bank_account(
	company: str,
	account_name: str,
	bank: str | None = None,
	parent_account: str | None = None,
	opening_balance: float = 0.0,
	add_to_policy: bool = True,
	account_type: str | None = None,
	is_default: bool = False,
	bank_account_no: str | None = None,
	allow_when_remote: bool = False,
) -> dict[str, Any]:
	"""
	Create a LYQD Bank Account (no Chart of Accounts).

	``parent_account`` is ignored (legacy ERPNext CoA arg).
	When Other Site is on, manual Add is blocked unless allow_when_remote (mirror path).
	"""
	_ = parent_account
	from lyqd.recommendations.settings import get_integration_settings, is_remote_source

	company = company or _default_lyqd_company()
	if is_remote_source(company) and not allow_when_remote:
		url = get_integration_settings(company).get("remote_site_url") or frappe._(
			"the remote site"
		)
		frappe.throw(
			frappe._(
				"Bank accounts are mirrored from {0}. Add company Bank Accounts there, then reconnect / reload."
			).format(url)
		)

	if not company:
		frappe.throw(frappe._("Company is required"))
	if not frappe.db.exists("LYQD Company", company):
		frappe.throw(frappe._("LYQD Company {0} not found").format(company))

	account_name = (account_name or "").strip()
	if not account_name:
		frappe.throw(frappe._("Account name is required"))

	existing = frappe.db.get_value(
		"LYQD Bank Account",
		{"company": company, "account_name": account_name},
		"name",
	)
	created = False
	if existing:
		ba_name = existing
	else:
		doc = frappe.get_doc(
			{
				"doctype": "LYQD Bank Account",
				"company": company,
				"account_name": account_name,
				"bank": (bank or "").strip() or None,
				"account_type": account_type or None,
				"is_default": 1 if is_default else 0,
				"bank_account_no": bank_account_no or None,
				"is_active": 1,
			}
		)
		doc.insert(ignore_permissions=True)
		ba_name = doc.name
		created = True

	if flt(opening_balance):
		set_statement_balance(ba_name, flt(opening_balance), today())

	if add_to_policy and frappe.db.exists("LYQD Company", company):
		co = frappe.get_doc("LYQD Company", company)
		if ba_name not in [r.bank_account for r in (co.eligible_bank_accounts or [])]:
			co.append(
				"eligible_bank_accounts",
				{"bank_account": ba_name, "account_name": account_name},
			)
			co.save(ignore_permissions=True)

	return {
		"bank_account": ba_name,
		"gl_account": None,
		"account_name": account_name,
		"company": company,
		"bank": bank,
		"created_gl_account": False,
		"created_bank_account": created,
	}


def _default_lyqd_company() -> str | None:
	from lyqd.setup.permissions import get_user_companies

	companies = get_user_companies()
	if companies:
		return companies[0]
	row = frappe.get_all("LYQD Company", filters={"is_active": 1}, limit=1, pluck="name")
	return row[0] if row else None
