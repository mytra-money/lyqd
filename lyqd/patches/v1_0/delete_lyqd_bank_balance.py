"""Remove unused LYQD Bank Balance — balances live on ERPNext Bank Account Balance."""

from __future__ import annotations

import frappe


def execute():
	if frappe.db.exists("DocType", "LYQD Bank Balance"):
		frappe.delete_doc("DocType", "LYQD Bank Balance", force=1, ignore_missing=True)
	# Orphan table may remain after DocType delete
	if frappe.db.table_exists("LYQD Bank Balance"):
		frappe.db.sql_ddl("drop table if exists `tabLYQD Bank Balance`")
