# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LYQDPaymentCategory(Document):
	def validate(self):
		self.category_name = (self.category_name or "").strip()
		if not self.category_name:
			frappe.throw(frappe._("Category Name is required"))
		if not int(self.allow_outflow or 0) and not int(self.allow_inflow or 0):
			frappe.throw(frappe._("Enable Outflow and/or Inflow for this category."))

		# Unique label per company (case-insensitive), independent of docname.
		existing = frappe.db.sql(
			"""
			select name from `tabLYQD Payment Category`
			where company = %s
				and lower(category_name) = %s
				and name != %s
			limit 1
			""",
			(self.company, self.category_name.lower(), self.name or ""),
		)
		if existing:
			frappe.throw(
				frappe._("Category {0} already exists for this company.").format(
					self.category_name
				)
			)
