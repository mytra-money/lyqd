"""Copy Singles books/investment fields onto each LYQD Company, then drop them from Singles."""

from __future__ import annotations

import frappe


def execute():
	if not frappe.db.exists("DocType", "LYQD Company"):
		return

	# Read legacy Singles columns if still present (pre thin Settings)
	legacy = _read_legacy_singles()
	companies = frappe.get_all("LYQD Company", pluck="name")
	if not companies:
		# Ensure at least one company can receive legacy values later via migrate_to_lyqd_company
		return

	for name in companies:
		_apply_to_company(name, legacy)

	# Drop obsolete Singles columns after copy (idempotent)
	_drop_singles_columns(
		[
			"investment_account_activated",
			"investment_account_crm_lead",
			"investment_account_requested_on",
			"erpnext_integration_enabled",
			"erpnext_source",
			"remote_site_url",
			"remote_company",
			"remote_api_key",
			"remote_api_secret",
		]
	)


def _singles_value(field: str):
	# Singles has no creation column — avoid ORM order_by
	return frappe.db.sql(
		"select value from tabSingles where doctype=%s and field=%s limit 1",
		("LYQD Settings", field),
	)


def _read_legacy_singles() -> dict:
	"""Read from Singles rows — works even after fields were removed from the DocType JSON."""
	out = {
		"enabled": 0,
		"source": "This Site",
		"remote_site_url": None,
		"remote_company": None,
		"remote_api_key": None,
		"remote_api_secret": None,
		"investment_account_activated": 0,
		"investment_account_requested_on": None,
		"investment_account_crm_lead": None,
	}
	if not frappe.db.exists("DocType", "LYQD Settings"):
		return out

	def _val(field, default=None):
		rows = _singles_value(field)
		if not rows:
			return default
		return rows[0][0]

	out["enabled"] = int(_val("erpnext_integration_enabled") or 0)
	out["source"] = (_val("erpnext_source") or "This Site").strip() or "This Site"
	out["remote_site_url"] = (_val("remote_site_url") or "").strip() or None
	out["remote_company"] = (_val("remote_company") or "").strip() or None
	out["remote_api_key"] = (_val("remote_api_key") or "").strip() or None
	out["investment_account_activated"] = int(_val("investment_account_activated") or 0)
	out["investment_account_requested_on"] = _val("investment_account_requested_on")
	out["investment_account_crm_lead"] = _val("investment_account_crm_lead")

	try:
		from frappe.utils.password import get_decrypted_password

		out["remote_api_secret"] = get_decrypted_password(
			"LYQD Settings", "LYQD Settings", fieldname="remote_api_secret", raise_exception=False
		)
	except Exception:
		out["remote_api_secret"] = None
	return out


def _apply_to_company(name: str, legacy: dict):
	co = frappe.get_doc("LYQD Company", name)
	changed = False

	# Only fill books when still Manual / blank (don't clobber per-company already set)
	current_books = co.books_source or "Manual"
	if current_books == "Manual" and legacy.get("enabled"):
		if legacy.get("source") == "Other Site":
			co.books_source = "Other Site"
			co.books_company = legacy.get("remote_company") or co.books_company or name
		else:
			co.books_source = "This Site"
			co.books_company = co.books_company or name
		changed = True
	elif not (co.books_company or "").strip():
		co.books_company = legacy.get("remote_company") or name
		changed = True

	# Always backfill remote credentials when missing (companies may already be Other Site)
	if (co.books_source or "") == "Other Site" or (
		legacy.get("enabled") and legacy.get("source") == "Other Site"
	):
		if legacy.get("remote_site_url") and not (co.remote_site_url or "").strip():
			co.remote_site_url = legacy["remote_site_url"]
			changed = True
		if legacy.get("remote_api_key") and not (co.remote_api_key or "").strip():
			co.remote_api_key = legacy["remote_api_key"]
			changed = True
		if legacy.get("remote_api_secret") and not co.get_password(
			"remote_api_secret", raise_exception=False
		):
			co.remote_api_secret = legacy["remote_api_secret"]
			changed = True
		if legacy.get("remote_company") and not (co.books_company or "").strip():
			co.books_company = legacy["remote_company"]
			changed = True

	# Investment: copy site-wide activation onto every company that hasn't been stamped
	if legacy.get("investment_account_activated") and not int(co.investment_account_activated or 0):
		co.investment_account_activated = 1
		changed = True
	if legacy.get("investment_account_requested_on") and not co.investment_account_requested_on:
		co.investment_account_requested_on = legacy["investment_account_requested_on"]
		changed = True
	if legacy.get("investment_account_crm_lead") and not co.investment_account_crm_lead:
		co.investment_account_crm_lead = legacy["investment_account_crm_lead"]
		changed = True

	if changed:
		co.flags.ignore_validate = True
		co.save(ignore_permissions=True)


def _drop_singles_columns(fields: list[str]):
	"""Remove obsolete Singles rows so Desk/API stop seeing stale values."""
	for field in fields:
		frappe.db.delete("Singles", {"doctype": "LYQD Settings", "field": field})
