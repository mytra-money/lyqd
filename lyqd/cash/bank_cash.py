"""Eligible bank cash for LYQD surplus — prefers ERPNext bank figures, never invents cash."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import flt, getdate, today


def get_policy_selected_bank_accounts(company: str) -> list[str] | None:
	"""Return selected Bank Account names from LYQD Policy, or None if all company accounts apply."""
	policy_name = frappe.db.get_value("LYQD Policy", {"company": company})
	if not policy_name:
		return None
	selected = frappe.get_all(
		"LYQD Policy Bank Account",
		filters={"parent": policy_name, "parenttype": "LYQD Policy"},
		pluck="bank_account",
	)
	# Empty table = include all company bank accounts (backward compatible).
	return selected or None


def get_company_bank_accounts(
	company: str,
	selected: list[str] | None = None,
) -> list[dict[str, Any]]:
	"""Company bank accounts eligible for surplus cash (this site or mirrored Other Site)."""
	from lyqd.recommendations.settings import is_remote_source

	if is_remote_source():
		from lyqd.cash.mirror_banks import (
			list_mirrored_local_bank_accounts,
			mirror_remote_bank_accounts,
		)

		# Keep local mirrors in sync with remote Chart of Bank Accounts (read-only remote)
		mirror_remote_bank_accounts(company)
		return list_mirrored_local_bank_accounts(company, selected=selected)

	filters: dict[str, Any] = {
		"company": company,
		"is_company_account": 1,
		"disabled": 0,
	}
	if selected:
		filters["name"] = ("in", selected)

	# Same company-account filters and enrichment shape as ERPNext Banking's get_list.
	rows = frappe.get_all(
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
	)
	for row in rows:
		row["account_currency"] = None
		row["books_source"] = "This Site"
		row["books_company"] = company
		if row.get("account"):
			row["account_currency"] = frappe.db.get_value("Account", row["account"], "account_currency")
	return rows


def get_statement_balance(bank_account: str, as_of: str | None = None) -> dict[str, Any]:
	"""ERPNext Banking statement closing — sole cash source for LYQD surplus."""
	as_of = str(getdate(as_of or today()))
	if not frappe.db.exists("DocType", "Bank Account Balance"):
		return {"balance": 0.0, "balance_date": None, "as_of": as_of}

	from erpnext.accounts.doctype.bank_account.bank_account import get_closing_balance_as_per_statement

	msg = get_closing_balance_as_per_statement(bank_account, as_of) or {}
	return {
		"balance": flt(msg.get("balance")),
		"balance_date": msg.get("date"),
		"as_of": as_of,
	}


def get_latest_bank_account_balance(bank_account: str, as_of: str | None = None) -> float | None:
	"""Compat: numeric statement balance (0 is valid; None only if DocType missing)."""
	if not frappe.db.exists("DocType", "Bank Account Balance"):
		return None
	return flt(get_statement_balance(bank_account, as_of)["balance"])


def set_statement_balance_local_only(
	bank_account: str, balance: float, as_of: str | None = None
) -> dict[str, Any]:
	"""Always write Bank Account Balance on this site (never the remote Other Site)."""
	as_of_d = getdate(as_of or today())
	from erpnext.accounts.doctype.bank_account.bank_account import (
		_set_closing_balance_as_per_statement,
	)

	_set_closing_balance_as_per_statement(bank_account, as_of_d, flt(balance))
	name = frappe.db.exists("Bank Account Balance", {"bank_account": bank_account, "date": as_of_d})
	return {
		"bank_account": bank_account,
		"date": str(as_of_d),
		"balance": flt(balance),
		"name": name,
		"source": "local_bab",
	}


def set_statement_balance(bank_account: str, balance: float, as_of: str | None = None) -> dict[str, Any]:
	"""Upsert statement closing on this LYQD site only — Other Site is read-only."""
	return set_statement_balance_local_only(bank_account, balance, as_of)


def resolve_bank_account_cash(
	bank_account_row: dict[str, Any],
	company: str,
	as_of: str | None = None,
) -> dict[str, Any]:
	"""
	Resolve cash for one Bank Account from ERPNext Bank Account Balance only
	(same DocType Banking edits for statement closing).
	"""
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
		"source": "Bank Account Balance",
		"books_source": bank_account_row.get("books_source") or "This Site",
		"books_company": bank_account_row.get("books_company") or company,
	}


def get_eligible_bank_cash(company: str, as_of: str | None = None) -> dict[str, Any]:
	"""Sum eligible company bank cash with per-account explanation rows."""
	from lyqd.recommendations.settings import is_remote_source

	selected = get_policy_selected_bank_accounts(company)
	as_of_s = str(getdate(as_of or today()))

	if is_remote_source():
		from lyqd.cash.mirror_banks import list_mirrored_local_bank_accounts, mirror_remote_bank_accounts
		from lyqd.recommendations.settings import get_integration_settings

		settings = get_integration_settings()
		try:
			mirror = mirror_remote_bank_accounts(company)
			accounts = list_mirrored_local_bank_accounts(company, selected=selected)
			books_company = mirror.get("books_company") or settings.get("remote_company")
		except Exception as e:
			frappe.log_error(title="LYQD remote bank mirror failed")
			return {
				"company": company,
				"books_company": settings.get("remote_company"),
				"books_source": "Other Site",
				"as_of": as_of_s,
				"total": 0.0,
				"accounts": [],
				"selection": "policy" if selected else "all_company_accounts",
				"selected_bank_accounts": selected or [],
				"balance_source": "this_site",
				"message": str(e),
			}

		rows: list[dict[str, Any]] = []
		total = 0.0
		for ba in accounts:
			row = resolve_bank_account_cash(ba, company, as_of_s)
			row["books_source"] = "Other Site"
			row["books_company"] = books_company
			row["remote_bank_account"] = ba.get("remote_bank_account") or ba.get(
				"lyqd_remote_bank_account"
			)
			rows.append(row)
			total += flt(row["balance"])

		return {
			"company": company,
			"books_company": books_company,
			"books_source": "Other Site",
			"as_of": as_of_s,
			"total": flt(total),
			"accounts": rows,
			"selection": "policy" if selected else "all_company_accounts",
			"selected_bank_accounts": selected or [],
			"balance_source": "this_site",
			"message": mirror.get("message") if not accounts else None,
			"mirrored": {"created": mirror.get("created"), "updated": mirror.get("updated")},
		}

	accounts = get_company_bank_accounts(company, selected=selected)
	rows = []
	total = 0.0
	for ba in accounts:
		row = resolve_bank_account_cash(ba, company, as_of)
		rows.append(row)
		total += flt(row["balance"])

	return {
		"company": company,
		"books_company": company,
		"books_source": "This Site",
		"as_of": as_of_s,
		"total": flt(total),
		"accounts": rows,
		"selection": "policy" if selected else "all_company_accounts",
		"selected_bank_accounts": selected or [],
		"balance_source": "this_site",
		"message": None,
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
	Create ERPNext masters the same way Banking/Plaid expect them:

	1. Chart of Accounts leaf Account (account_type = Bank)
	2. Bank master (if missing)
	3. Bank Account with is_company_account = 1 linked to that GL

	Intended for sites that do not already have bank masters set up.
	When Other Site is on, manual Add is blocked unless allow_when_remote (mirror path).
	"""
	from lyqd.recommendations.settings import get_integration_settings, is_remote_source

	if is_remote_source() and not allow_when_remote:
		url = get_integration_settings().get("remote_site_url") or frappe._("the remote site")
		frappe.throw(
			frappe._(
				"Bank accounts are mirrored from {0}. Add company Bank Accounts there, then reconnect / reload."
			).format(url)
		)

	company = company or frappe.defaults.get_user_default("Company")
	if not company:
		frappe.throw(frappe._("Company is required"))
	account_name = (account_name or "").strip()
	if not account_name:
		frappe.throw(frappe._("Account name is required"))

	if not parent_account:
		parent_account = frappe.db.get_value(
			"Account",
			{"company": company, "is_group": 1, "account_type": "Bank"},
			"name",
		) or frappe.db.get_value(
			"Account",
			{"company": company, "is_group": 1, "account_name": ("like", "%Bank%")},
			"name",
		)
	if not parent_account:
		frappe.throw(
			frappe._("No Bank group account found in Chart of Accounts for {0}").format(company)
		)

	gl_name = frappe.db.get_value(
		"Account",
		{"company": company, "account_name": account_name, "is_group": 0},
		"name",
	)
	created_gl = False
	if not gl_name:
		gl = frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": account_name,
				"parent_account": parent_account,
				"company": company,
				"account_type": "Bank",
				"is_group": 0,
			}
		)
		gl.insert()
		gl_name = gl.name
		created_gl = True

	bank_name = (bank or "").strip() or "Operating Bank"
	if not frappe.db.exists("Bank", bank_name):
		frappe.get_doc({"doctype": "Bank", "bank_name": bank_name}).insert()

	existing_ba = frappe.db.get_value(
		"Bank Account",
		{"company": company, "account": gl_name, "is_company_account": 1},
		"name",
	)
	created_ba = False
	if existing_ba:
		ba_name = existing_ba
	else:
		if is_default:
			# Only one default company bank account
			frappe.db.set_value(
				"Bank Account",
				{"company": company, "is_company_account": 1, "is_default": 1},
				"is_default",
				0,
			)
		ba = frappe.get_doc(
			{
				"doctype": "Bank Account",
				"account_name": account_name,
				"account": gl_name,
				"company": company,
				"is_company_account": 1,
				"bank": bank_name,
				"account_type": account_type or None,
				"is_default": 1 if is_default else 0,
				"bank_account_no": bank_account_no or None,
			}
		)
		ba.insert()
		ba_name = ba.name
		created_ba = True

	if flt(opening_balance):
		set_statement_balance(ba_name, flt(opening_balance), today())

	if add_to_policy:
		policy_name = frappe.db.get_value("LYQD Policy", {"company": company})
		if policy_name:
			policy = frappe.get_doc("LYQD Policy", policy_name)
			if ba_name not in [r.bank_account for r in policy.eligible_bank_accounts]:
				policy.append(
					"eligible_bank_accounts",
					{"bank_account": ba_name, "account_name": account_name, "gl_account": gl_name},
				)
				policy.save()

	return {
		"bank_account": ba_name,
		"gl_account": gl_name,
		"account_name": account_name,
		"company": company,
		"bank": bank_name,
		"created_gl_account": created_gl,
		"created_bank_account": created_ba,
	}
