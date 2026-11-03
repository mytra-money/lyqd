"""
Create LYQD Company + LYQD Bank Account/Balance from legacy ERPNext Company usage.

Keeps the same company *name* so existing Link values (Policy, plan, etc.) resolve
after field options change from Company → LYQD Company.
"""

from __future__ import annotations

import frappe
from frappe.utils import flt


def execute():
	if not frappe.db.exists("DocType", "LYQD Company"):
		return

	# Collect company names referenced by LYQD docs
	names: set[str] = set()
	for dt in (
		"LYQD Policy",
		"LYQD Upcoming Payment",
		"LYQD Draft Proposal",
		"LYQD Investment Instruction",
		"LYQD Holding",
		"LYQD Surplus Run",
		"LYQD Cash Snapshot",
	):
		if frappe.db.exists("DocType", dt) and frappe.db.has_column(dt, "company"):
			names.update(frappe.get_all(dt, pluck="company") or [])

	settings = frappe.get_single("LYQD Settings") if frappe.db.exists("DocType", "LYQD Settings") else None
	remote_on = bool(
		settings
		and settings.get("erpnext_integration_enabled")
		and (settings.get("erpnext_source") or "") == "Other Site"
	)
	remote_company = (settings.get("remote_company") if settings else None) or None

	for name in sorted(n for n in names if n):
		if frappe.db.exists("LYQD Company", name):
			continue
		abbr = None
		currency = "INR"
		if frappe.db.exists("DocType", "Company") and frappe.db.exists("Company", name):
			row = frappe.db.get_value("Company", name, ["abbr", "default_currency"], as_dict=True)
			if row:
				abbr = row.abbr
				currency = row.default_currency or "INR"
		books_source = "Other Site" if remote_on else ("This Site" if frappe.db.exists("DocType", "Company") else "Manual")
		books_company = remote_company if remote_on else name
		doc = frappe.get_doc(
			{
				"doctype": "LYQD Company",
				"company_name": name,
				"abbr": abbr,
				"is_active": 1,
				"default_currency": currency,
				"books_source": books_source,
				"books_company": books_company,
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()

	_migrate_banks()


def _migrate_banks():
	if not frappe.db.exists("DocType", "LYQD Bank Account"):
		return
	if not frappe.db.exists("DocType", "Bank Account"):
		return

	# Prefer banks already on policies
	policy_bas = set()
	if frappe.db.exists("DocType", "LYQD Policy Bank Account"):
		policy_bas.update(
			frappe.get_all("LYQD Policy Bank Account", pluck="bank_account") or []
		)

	filters = {"is_company_account": 1, "disabled": 0}
	rows = frappe.get_all(
		"Bank Account",
		filters=filters,
		fields=[
			"name",
			"account_name",
			"company",
			"bank",
			"account_type",
			"bank_account_no",
			"is_default",
			"lyqd_remote_bank_account",
		],
	)
	for ba in rows:
		company = ba.company
		if not company or not frappe.db.exists("LYQD Company", company):
			continue
		# Skip if already migrated (matched by books_bank_account or same account_name)
		if frappe.db.exists(
			"LYQD Bank Account",
			{"company": company, "books_bank_account": ba.name},
		) or frappe.db.exists(
			"LYQD Bank Account",
			{"company": company, "account_name": ba.account_name or ba.name},
		):
			# Ensure books mapping
			existing = frappe.db.get_value(
				"LYQD Bank Account",
				{"company": company, "account_name": ba.account_name or ba.name},
				"name",
			) or frappe.db.get_value(
				"LYQD Bank Account",
				{"company": company, "books_bank_account": ba.name},
				"name",
			)
			if existing and ba.get("lyqd_remote_bank_account"):
				frappe.db.set_value(
					"LYQD Bank Account",
					existing,
					"books_bank_account",
					ba.lyqd_remote_bank_account,
					update_modified=False,
				)
			elif existing:
				frappe.db.set_value(
					"LYQD Bank Account",
					existing,
					"books_bank_account",
					ba.name,
					update_modified=False,
				)
			_copy_balances(ba.name, existing)
			_remap_policy_row(company, ba.name, existing)
			continue

		# Only migrate if on a policy or has remote mapping / any balance
		has_remote = bool(ba.get("lyqd_remote_bank_account"))
		on_policy = ba.name in policy_bas
		if not (has_remote or on_policy):
			# Still migrate if company has LYQD Policy (cash management company)
			if not frappe.db.exists("LYQD Policy", {"company": company}):
				continue

		doc = frappe.get_doc(
			{
				"doctype": "LYQD Bank Account",
				"company": company,
				"account_name": ba.account_name or ba.name,
				"bank": ba.bank,
				"account_type": ba.account_type,
				"bank_account_no": ba.bank_account_no,
				"is_default": 1 if ba.is_default else 0,
				"is_active": 1,
				"books_bank_account": ba.get("lyqd_remote_bank_account") or ba.name,
			}
		)
		doc.insert(ignore_permissions=True)
		_copy_balances(ba.name, doc.name)
		_remap_policy_row(company, ba.name, doc.name)


def _copy_balances(erpnext_ba: str, lyqd_ba: str):
	if not frappe.db.exists("DocType", "Bank Account Balance"):
		return
	if not frappe.db.exists("DocType", "LYQD Bank Balance"):
		return
	rows = frappe.get_all(
		"Bank Account Balance",
		filters={"bank_account": erpnext_ba},
		fields=["date", "balance"],
		order_by="date asc",
	)
	company = frappe.db.get_value("LYQD Bank Account", lyqd_ba, "company")
	for r in rows:
		if frappe.db.exists(
			"LYQD Bank Balance", {"bank_account": lyqd_ba, "date": r.date}
		):
			continue
		frappe.get_doc(
			{
				"doctype": "LYQD Bank Balance",
				"bank_account": lyqd_ba,
				"company": company,
				"date": r.date,
				"balance": flt(r.balance),
			}
		).insert(ignore_permissions=True)


def _remap_policy_row(company: str, old_ba: str, new_ba: str):
	policy_name = frappe.db.get_value("LYQD Policy", {"company": company})
	if not policy_name:
		return
	frappe.db.sql(
		"""
		update `tabLYQD Policy Bank Account`
		set bank_account = %s
		where parent = %s and bank_account = %s
		""",
		(new_ba, policy_name, old_ba),
	)
