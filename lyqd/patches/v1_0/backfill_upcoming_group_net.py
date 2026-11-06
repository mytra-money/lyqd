# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

"""Persist signed nest totals on Account-group plan roots."""

import frappe


def execute():
	if not frappe.db.exists("DocType", "LYQD Upcoming Payment"):
		return
	if not frappe.db.has_column("LYQD Upcoming Payment", "group_net"):
		return

	from lyqd.recommendations.core import refresh_upcoming_group_net

	# Currency is NOT NULL — nested children / non-nests use 0
	frappe.db.sql(
		"""
		UPDATE `tabLYQD Upcoming Payment`
		SET group_net = 0
		WHERE IFNULL(parent_payment, '') != ''
		"""
	)

	roots = frappe.get_all(
		"LYQD Upcoming Payment",
		filters={"parent_payment": ("in", ["", None])},
		pluck="name",
	)
	for name in roots:
		refresh_upcoming_group_net(name)
