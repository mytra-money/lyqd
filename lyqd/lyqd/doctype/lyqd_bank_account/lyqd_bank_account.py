# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LYQDBankAccount(Document):
	def validate(self):
		self.account_name = (self.account_name or "").strip()
		if not self.account_name:
			frappe.throw(frappe._("Account Name is required"))
		if self.is_default:
			frappe.db.sql(
				"""
				update `tabLYQD Bank Account`
				set is_default = 0
				where company = %s and name != %s and ifnull(is_default, 0) = 1
				""",
				(self.company, self.name or ""),
			)
