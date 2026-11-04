"""Mirror Other Site company Bank Accounts onto LYQD Bank Account (read remote, write local only)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import flt, getdate, today


def list_mirrored_local_bank_accounts(
	local_company: str,
	selected: list[str] | None = None,
) -> list[dict[str, Any]]:
	"""LYQD Bank Accounts for company that have a books_bank_account mapping."""
	filters: dict[str, Any] = {
		"company": local_company,
		"is_active": 1,
		"books_bank_account": ("is", "set"),
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

	if selected and not rows:
		rows = frappe.get_all(
			"LYQD Bank Account",
			filters={
				"company": local_company,
				"is_active": 1,
				"books_bank_account": ("in", selected),
			},
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

	books_company = frappe.db.get_value("LYQD Company", local_company, "books_company")
	for row in rows:
		row["account"] = None
		row["account_currency"] = row.get("currency")
		row["books_source"] = "Other Site"
		row["books_company"] = books_company
		row["remote_bank_account"] = row.get("books_bank_account")
	return rows


def mirror_remote_bank_accounts(local_company: str) -> dict[str, Any]:
	"""
	Create/update LYQD Bank Account for each remote company bank account.

	Never writes to the remote site. Mirrors account masters only — balances stay on
	local LYQD Bank Balance (updated from /lyqd/cash), never fetched from remote.
	"""
	local_company = local_company or _default_company()
	if not local_company:
		frappe.throw(frappe._("Company is required to mirror remote bank accounts"))
	if not frappe.db.exists("LYQD Company", local_company):
		frappe.throw(frappe._("LYQD Company {0} not found").format(local_company))

	from lyqd.cash.remote_banks import list_remote_bank_accounts
	from lyqd.recommendations.remote import get_remote_client

	_client, books_company = get_remote_client(local_company)
	# Keep books mapping on the LYQD Company
	frappe.db.set_value(
		"LYQD Company",
		local_company,
		{
			"books_source": "Other Site",
			"books_company": books_company,
		},
		update_modified=False,
	)

	remote_rows = list_remote_bank_accounts(lyqd_company=local_company)

	created = 0
	updated = 0
	errors: list[str] = []
	accounts: list[dict[str, Any]] = []

	for remote in remote_rows:
		try:
			local_name, was_created = _ensure_mirrored_bank_account(local_company, remote)
		except Exception as e:
			errors.append(f"{remote.get('name')}: {e}")
			frappe.log_error(title="LYQD mirror bank account failed")
			continue
		if was_created:
			created += 1
		else:
			updated += 1

		accounts.append(
			{
				"name": local_name,
				"account_name": remote.get("account_name") or local_name,
				"remote_bank_account": remote["name"],
				"bank": remote.get("bank"),
				"is_default": remote.get("is_default"),
				"books_source": "Other Site",
				"books_company": books_company,
			}
		)

	_remap_policy_bank_accounts(local_company)

	message = None
	if not remote_rows:
		from lyqd.recommendations.settings import get_integration_settings

		url = get_integration_settings(local_company).get("remote_site_url") or "the remote ERPNext site"
		message = frappe._(
			"No company bank accounts on {0}. Add Bank Accounts there (company account = Yes), then reconnect."
		).format(url)

	if errors and not message:
		message = frappe._("Some remote banks could not be mirrored: {0}").format("; ".join(errors[:3]))

	return {
		"company": local_company,
		"books_company": books_company,
		"created": created,
		"updated": updated,
		"accounts": accounts,
		"errors": errors,
		"message": message,
		"balance_source": "lyqd",
		"remote_bab_available": False,
	}


def _ensure_mirrored_bank_account(local_company: str, remote: dict[str, Any]) -> tuple[str, bool]:
	remote_name = remote["name"]
	account_name = (remote.get("account_name") or remote_name or "").strip()
	if not account_name:
		frappe.throw(frappe._("Remote bank account is missing an account name"))

	currency = (remote.get("account_currency") or remote.get("currency") or "").upper() or None

	existing = frappe.db.get_value(
		"LYQD Bank Account",
		{"company": local_company, "books_bank_account": remote_name},
		"name",
	)
	if existing:
		if currency:
			frappe.db.set_value(
				"LYQD Bank Account", existing, "currency", currency, update_modified=False
			)
		return existing, False

	by_name = frappe.db.get_value(
		"LYQD Bank Account",
		{"company": local_company, "account_name": account_name},
		"name",
	)
	if by_name:
		updates = {"books_bank_account": remote_name}
		if currency:
			updates["currency"] = currency
		frappe.db.set_value("LYQD Bank Account", by_name, updates, update_modified=False)
		return by_name, False

	doc = frappe.get_doc(
		{
			"doctype": "LYQD Bank Account",
			"company": local_company,
			"account_name": account_name,
			"bank": remote.get("bank"),
			"account_type": remote.get("account_type"),
			"bank_account_no": remote.get("bank_account_no"),
			"currency": currency or "INR",
			"is_default": 1 if remote.get("is_default") else 0,
			"is_active": 1,
			"books_bank_account": remote_name,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name, True


def _remap_policy_bank_accounts(local_company: str) -> None:
	"""Map company Policy rows that still store remote bank names → local LYQD Bank Account names."""
	if not frappe.db.exists("LYQD Company", local_company):
		return
	co = frappe.get_doc("LYQD Company", local_company)
	changed = False
	for row in co.eligible_bank_accounts or []:
		ba = (row.bank_account or "").strip()
		if not ba:
			continue
		if frappe.db.exists("LYQD Bank Account", ba):
			continue
		mapped = frappe.db.get_value(
			"LYQD Bank Account",
			{"company": local_company, "books_bank_account": ba},
			"name",
		)
		if mapped:
			row.bank_account = mapped
			row.account_name = frappe.db.get_value("LYQD Bank Account", mapped, "account_name")
			changed = True
	if changed:
		co.save(ignore_permissions=True)


def ensure_bank_account_custom_fields() -> None:
	"""No-op — LYQD Bank Account owns books_bank_account; kept for install hook compat."""
	return


def _default_company() -> str | None:
	from lyqd.setup.permissions import get_user_companies

	companies = get_user_companies()
	if companies:
		return companies[0]
	row = frappe.get_all("LYQD Company", filters={"is_active": 1}, limit=1, pluck="name")
	return row[0] if row else None
