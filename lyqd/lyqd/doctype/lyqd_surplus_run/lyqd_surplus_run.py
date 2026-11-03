# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LYQDSurplusRun(Document):
	"""Immutable free-cash calculation used as the source for investment requests."""

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from lyqd.lyqd.doctype.lyqd_surplus_run_line.lyqd_surplus_run_line import LYQDSurplusRunLine

		as_of: DF.Date
		bank_cash: DF.Currency
		company: DF.Link
		explanation_json: DF.Code | None
		horizon_days: DF.Int
		horizon_end: DF.Date | None
		investable_surplus: DF.Currency
		is_shortfall: DF.Check
		lines: DF.Table[LYQDSurplusRunLine]
		min_liquidity_buffer: DF.Currency
		naming_series: DF.Literal["LYQD-SR-.YYYY.-.#####"]
		policy: DF.Link | None
		restricted_cash: DF.Currency
		upcoming_total: DF.Currency
	# end: auto-generated types

	def on_trash(self):
		linked = frappe.db.exists("LYQD Draft Proposal", {"surplus_run": self.name})
		if linked:
			frappe.throw(
				frappe._("Cannot delete Surplus Run {0} — linked to investment request {1}.").format(
					self.name, linked
				)
			)
