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
		cash_effect: DF.Literal["Outflow", "Setoff"]
		category: DF.Literal["Salary", "Import-LC", "Vendor", "Customer", "Tax", "Loan", "Other"]
		company: DF.Link
		due_date: DF.Date
		last_synced_on: DF.Datetime | None
		naming_series: DF.Literal["LYQD-UP-.YYYY.-.#####"]
		notes: DF.SmallText | None
		parent_payment: DF.Link | None
		source_account: DF.Data | None
		source_doctype: DF.Data | None
		source_name: DF.Data | None
		status: DF.Literal["Planned", "Paid", "Cancelled"]
		title: DF.Data
	# end: auto-generated types

	def validate(self):
		if self.amount is not None and self.amount < 0:
			frappe.throw(frappe._("Amount cannot be negative"))
		if self.parent_payment:
			if self.parent_payment == self.name:
				frappe.throw(frappe._("Payment cannot be its own parent."))
			parent = frappe.db.get_value(
				"LYQD Upcoming Payment",
				self.parent_payment,
				["company", "parent_payment"],
				as_dict=True,
			)
			if not parent:
				frappe.throw(frappe._("Parent payment {0} not found.").format(self.parent_payment))
			if parent.company != self.company:
				frappe.throw(frappe._("Parent payment must belong to the same company."))
			if parent.parent_payment:
				frappe.throw(frappe._("Only one level of plan nesting is allowed."))
			# Child due date locked to parent
			parent_due = frappe.db.get_value("LYQD Upcoming Payment", self.parent_payment, "due_date")
			if parent_due:
				self.due_date = parent_due

	def on_update(self):
		# Cascade due date to Planned children when this row is a parent
		if self.has_value_changed("due_date") and self.due_date and not self.parent_payment:
			children = frappe.get_all(
				"LYQD Upcoming Payment",
				filters={
					"parent_payment": self.name,
					"status": "Planned",
				},
				pluck="name",
			)
			for child_name in children:
				frappe.db.set_value(
					"LYQD Upcoming Payment",
					child_name,
					"due_date",
					self.due_date,
					update_modified=True,
				)
