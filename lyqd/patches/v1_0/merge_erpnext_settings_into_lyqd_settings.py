"""Copy LYQD ERPNext Settings into LYQD Settings, then drop the separate Single.

Reads legacy Singles via SQL so it still works after the Python module is removed.
"""

from __future__ import annotations

import frappe


def execute():
	if not frappe.db.exists("DocType", "LYQD Settings"):
		return

	meta = frappe.get_meta("LYQD Settings", cached=False)
	if not meta.has_field("erpnext_integration_enabled"):
		return

	legacy_name = "LYQD ERPNext Settings"
	if frappe.db.exists("DocType", legacy_name):
		rows = frappe.db.sql(
			"select field, value from `tabSingles` where doctype=%s",
			legacy_name,
			as_dict=True,
		)
		data = {r.field: r.value for r in rows}
		settings = frappe.get_single("LYQD Settings")
		settings.erpnext_integration_enabled = 1 if cint(data.get("enabled")) else 0
		settings.erpnext_source = data.get("source") or "This Site"
		settings.remote_site_url = data.get("remote_site_url") or settings.get("remote_site_url")
		settings.remote_company = data.get("remote_company") or settings.get("remote_company")
		settings.remote_api_key = data.get("remote_api_key") or settings.get("remote_api_key")
		try:
			secret = frappe.utils.password.get_decrypted_password(
				legacy_name, legacy_name, fieldname="remote_api_secret", raise_exception=False
			)
		except Exception:
			secret = None
		if secret:
			settings.remote_api_secret = secret
		settings.flags.ignore_validate = True
		settings.save(ignore_permissions=True)

		frappe.delete_doc("DocType", legacy_name, force=1, ignore_missing=True)
		frappe.db.sql("delete from `tabSingles` where doctype=%s", legacy_name)


def cint(v):
	from frappe.utils import cint as _cint

	return _cint(v)
