"""Remove LYQD Cash Snapshot — balances live on LYQD Bank Balance only."""

from __future__ import annotations

import frappe


def execute():
	if frappe.db.exists("DocType", "LYQD Cash Snapshot"):
		frappe.delete_doc("DocType", "LYQD Cash Snapshot", force=1, ignore_missing=True)
	# Orphan table if DocType was already removed from disk before migrate
	if frappe.db.table_exists("LYQD Cash Snapshot"):
		frappe.db.sql_ddl("drop table if exists `tabLYQD Cash Snapshot`")
	frappe.clear_cache()
