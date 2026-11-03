"""Backfill Draft Proposal.request_type and Investment Instruction.side defaults."""

from __future__ import annotations

import frappe


def execute():
	if frappe.db.exists("DocType", "LYQD Draft Proposal") and frappe.db.has_column(
		"LYQD Draft Proposal", "request_type"
	):
		frappe.db.sql(
			"""
			update `tabLYQD Draft Proposal`
			set request_type = 'Invest'
			where ifnull(request_type, '') = ''
			"""
		)

	if frappe.db.exists("DocType", "LYQD Investment Instruction") and frappe.db.has_column(
		"LYQD Investment Instruction", "side"
	):
		frappe.db.sql(
			"""
			update `tabLYQD Investment Instruction`
			set side = 'Purchase'
			where ifnull(side, '') = ''
			"""
		)
