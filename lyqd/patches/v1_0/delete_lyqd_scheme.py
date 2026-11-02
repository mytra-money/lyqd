"""Remove local LYQD Scheme catalogue — schemes come from Mytra."""

from __future__ import annotations

import frappe


def execute():
	if frappe.db.exists("DocType", "LYQD Scheme"):
		frappe.delete_doc("DocType", "LYQD Scheme", force=1, ignore_missing=True)
		frappe.clear_cache()
