# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

"""Seed LYQD Settings.in_beta = 1 (DocType default is not applied to existing Singles)."""

from __future__ import annotations

import frappe


def execute() -> None:
	if not frappe.db.exists("DocType", "LYQD Settings"):
		return
	frappe.db.set_single_value("LYQD Settings", "in_beta", 1, update_modified=False)
