# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LYQDHolding(Document):
	"""Optional local mirror of Mytra positions — SPA reads Mytra via get_portfolio."""

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amount: DF.Currency
		as_on: DF.Date
		company: DF.Link
		mytra_position_ref: DF.Data | None
		naming_series: DF.Literal["LYQD-HLD-.YYYY.-.#####"]
		nav: DF.Float
		notes: DF.SmallText | None
		scheme: DF.Data
		scheme_isin: DF.Data | None
		scheme_label: DF.Data | None
		source: DF.Literal["Mytra"]
		units: DF.Float
	# end: auto-generated types

	def validate(self):
		if self.amount is not None and self.amount < 0:
			frappe.throw(frappe._("Amount cannot be negative"))
