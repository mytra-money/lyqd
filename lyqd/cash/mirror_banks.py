"""Mirror Other Site company Bank Accounts onto this LYQD site (read remote, write local only)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import flt, getdate, today


REMOTE_BA_FIELD = "lyqd_remote_bank_account"


def ensure_bank_account_custom_fields() -> None:
	"""Track which local Bank Account was mirrored from the remote site."""
	if not frappe.db.exists("DocType", "Bank Account"):
		return
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(
		{
			"Bank Account": [
				{
					"fieldname": REMOTE_BA_FIELD,
					"label": "LYQD Remote Bank Account",
					"fieldtype": "Data",
					"insert_after": "account_name",
					"read_only": 1,
					"no_copy": 1,
					"translatable": 0,
					"description": "Name of the Bank Account on the configured Other Site (mirrored locally).",
				}
			]
		},
		ignore_validate=True,
		update=True,
	)


def list_mirrored_local_bank_accounts(
	local_company: str,
	selected: list[str] | None = None,
) -> list[dict[str, Any]]:
	"""Local company bank accounts that were mirrored from Other Site."""
	ensure_bank_account_custom_fields()
	filters: dict[str, Any] = {
		"company": local_company,
		"is_company_account": 1,
		"disabled": 0,
		REMOTE_BA_FIELD: ("is", "set"),
	}
	if selected:
		# Policy may store local name or legacy remote name
		filters["name"] = ("in", selected)

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
			"company",
			REMOTE_BA_FIELD,
		],
		order_by="is_default desc, account_name asc",
	)

	# If policy still has remote names, also match on the custom field
	if selected and not rows:
		rows = frappe.get_all(
			"Bank Account",
			filters={
				"company": local_company,
				"is_company_account": 1,
				"disabled": 0,
				REMOTE_BA_FIELD: ("in", selected),
			},
			fields=[
				"name",
				"account_name",
				"account",
				"bank",
				"is_default",
				"account_type",
				"account_subtype",
				"bank_account_no",
				"company",
				REMOTE_BA_FIELD,
			],
			order_by="is_default desc, account_name asc",
		)

	for row in rows:
		row["books_source"] = "Other Site"
		row["remote_bank_account"] = row.get(REMOTE_BA_FIELD)
		row["account_currency"] = None
		if row.get("account"):
			row["account_currency"] = frappe.db.get_value(
				"Account", row["account"], "account_currency"
			)
	return rows


def mirror_remote_bank_accounts(local_company: str) -> dict[str, Any]:
	"""
	Create/update local Bank Account (+ Bank + GL) for each remote company bank account.

	Never writes to the remote site. Optionally seeds local statement balance from a
	remote Bank Account Balance read when that DocType exists remotely and local is empty.
	"""
	ensure_bank_account_custom_fields()
	local_company = local_company or frappe.defaults.get_user_default("Company")
	if not local_company:
		local_company = frappe.db.get_single_value("Global Defaults", "default_company")
	if not local_company:
		frappe.throw(frappe._("Company is required to mirror remote bank accounts"))

	from lyqd.cash.remote_banks import (
		get_remote_statement_balance,
		list_remote_bank_accounts,
		remote_has_doctype,
	)
	from lyqd.recommendations.remote import get_remote_client

	client, books_company = get_remote_client()
	remote_rows = list_remote_bank_accounts()
	use_remote_bab = remote_has_doctype(client, "Bank Account Balance")

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

		if use_remote_bab:
			_seed_local_balance_from_remote_read(client, local_name, remote["name"])

		accounts.append(
			{
				"name": local_name,
				"account_name": remote.get("account_name") or local_name,
				"remote_bank_account": remote["name"],
				"account": frappe.db.get_value("Bank Account", local_name, "account"),
				"bank": remote.get("bank"),
				"is_default": remote.get("is_default"),
				"books_source": "Other Site",
				"books_company": books_company,
			}
		)

	# Remap policy selected banks from remote names → local names
	_remap_policy_bank_accounts(local_company)

	message = None
	if not remote_rows:
		from lyqd.recommendations.settings import get_integration_settings

		url = get_integration_settings().get("remote_site_url") or "the remote ERPNext site"
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
		"balance_source": "this_site",
		"remote_bab_available": use_remote_bab,
	}


def _ensure_mirrored_bank_account(local_company: str, remote: dict[str, Any]) -> tuple[str, bool]:
	remote_name = remote["name"]
	account_name = (remote.get("account_name") or remote_name or "").strip()
	if not account_name:
		frappe.throw(frappe._("Remote bank account is missing an account name"))

	existing = frappe.db.get_value(
		"Bank Account",
		{"company": local_company, REMOTE_BA_FIELD: remote_name},
		"name",
	)
	if existing:
		return existing, False

	# Reuse a same-named local company account if present
	by_name = frappe.db.get_value(
		"Bank Account",
		{"company": local_company, "name": remote_name, "is_company_account": 1},
		"name",
	)
	if by_name:
		frappe.db.set_value("Bank Account", by_name, REMOTE_BA_FIELD, remote_name)
		return by_name, False

	from lyqd.cash.bank_cash import create_company_bank_account

	account_type = (remote.get("account_type") or "").strip() or None
	# Account Type is a Link on some ERPNext versions — skip if not present locally
	if account_type and frappe.db.exists("DocType", "Account Type"):
		if not frappe.db.exists("Account Type", account_type):
			account_type = None
	elif account_type and not frappe.db.exists("DocType", "Account Type"):
		# Older sites: free-text — keep; if insert fails we retry without it below
		pass

	try:
		created = create_company_bank_account(
			company=local_company,
			account_name=account_name,
			bank=remote.get("bank"),
			account_type=account_type,
			bank_account_no=remote.get("bank_account_no"),
			is_default=bool(remote.get("is_default")),
			opening_balance=0,
			add_to_policy=False,
			allow_when_remote=True,
		)
	except Exception:
		# Retry without account_type / is_default if remote enums don't exist here
		created = create_company_bank_account(
			company=local_company,
			account_name=account_name,
			bank=remote.get("bank"),
			account_type=None,
			bank_account_no=remote.get("bank_account_no"),
			is_default=False,
			opening_balance=0,
			add_to_policy=False,
			allow_when_remote=True,
		)
	local_name = created["bank_account"]
	frappe.db.set_value("Bank Account", local_name, REMOTE_BA_FIELD, remote_name)
	return local_name, True


def _seed_local_balance_from_remote_read(client, local_bank_account: str, remote_bank_account: str) -> None:
	"""One-way read: if local has no balance for today, copy remote statement balance locally."""
	as_of = today()
	if frappe.db.exists(
		"Bank Account Balance", {"bank_account": local_bank_account, "date": as_of}
	):
		return
	try:
		stmt = get_remote_statement_balance(client, remote_bank_account, as_of)
	except Exception:
		return
	if not stmt.get("balance_date") and not flt(stmt.get("balance")):
		return
	from lyqd.cash.bank_cash import set_statement_balance_local_only

	# Use remote's balance date when available
	bal_date = stmt.get("balance_date") or as_of
	set_statement_balance_local_only(local_bank_account, flt(stmt.get("balance")), bal_date)


def _remap_policy_bank_accounts(local_company: str) -> None:
	policy_name = frappe.db.get_value("LYQD Policy", {"company": local_company})
	if not policy_name:
		return
	policy = frappe.get_doc("LYQD Policy", policy_name)
	dirty = False
	for row in policy.eligible_bank_accounts or []:
		name = row.bank_account
		if not name:
			continue
		if frappe.db.exists("Bank Account", name):
			continue
		local = frappe.db.get_value(
			"Bank Account",
			{"company": local_company, REMOTE_BA_FIELD: name},
			"name",
		)
		if local:
			row.bank_account = local
			row.account_name = frappe.db.get_value("Bank Account", local, "account_name")
			row.gl_account = frappe.db.get_value("Bank Account", local, "account")
			dirty = True
	if dirty:
		policy.save(ignore_permissions=True)
