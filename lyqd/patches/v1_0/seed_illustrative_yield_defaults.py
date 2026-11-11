# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

"""Seed Proposal illustration rates on LYQD Settings (Singles defaults are not auto-applied)."""

from __future__ import annotations

import frappe


def execute() -> None:
	if not frappe.db.exists("DocType", "LYQD Settings"):
		return
	defaults = {
		"illustrative_idle_yield_pct": 0,
		"illustrative_fd_yield_pct": 3,
		"illustrative_liquid_yield_pct": 5.5,
	}
	for field, value in defaults.items():
		if not frappe.db.exists("Singles", {"doctype": "LYQD Settings", "field": field}):
			frappe.db.set_single_value("LYQD Settings", field, value, update_modified=False)
