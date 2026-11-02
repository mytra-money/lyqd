# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LYQDUpcomingPayment(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amount: DF.Currency
		category: DF.Literal["Salary", "Import-LC", "Vendor", "Tax", "Loan", "Other"]
		company: DF.Link
		due_date: DF.Date
		naming_series: DF.Literal["LYQD-UP-.YYYY.-.#####"]
		notes: DF.SmallText | None
		status: DF.Literal["Planned", "Paid", "Cancelled"]
		title: DF.Data
	# end: auto-generated types

	def validate(self):
		if self.amount is not None and self.amount < 0:
			frappe.throw(frappe._("Amount cannot be negative"))
