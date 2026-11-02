# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LYQDHolding(Document):
	"""Manual / simulated holdings for PoC — no allotment API."""

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amount: DF.Currency
		as_on: DF.Date
		company: DF.Link
		naming_series: DF.Literal["LYQD-HLD-.YYYY.-.#####"]
		nav: DF.Float
		notes: DF.SmallText | None
		scheme: DF.Link
		source: DF.Literal["Manual", "Simulated"]
		units: DF.Float
	# end: auto-generated types

	def validate(self):
		if self.amount is not None and self.amount < 0:
			frappe.throw(frappe._("Amount cannot be negative"))
