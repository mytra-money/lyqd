"""Legacy cleanup — old Data-based LYQD Bank Balance (pre LYQD Bank Account Link).

The current LYQD Bank Balance DocType is intentional; do not delete it.
"""

from __future__ import annotations

import frappe


def execute():
	# Already migrated sites may have run the destructive version; no-op going forward.
	if not frappe.db.exists("DocType", "LYQD Bank Balance"):
		return
	meta = frappe.get_meta("LYQD Bank Balance", cached=False)
	field = meta.get_field("bank_account")
	# Only remove the obsolete Data-only version (no Link to LYQD Bank Account)
	if field and field.fieldtype == "Data":
		frappe.delete_doc("DocType", "LYQD Bank Balance", force=1, ignore_missing=True)
		if frappe.db.table_exists("LYQD Bank Balance"):
			frappe.db.sql_ddl("drop table if exists `tabLYQD Bank Balance`")
