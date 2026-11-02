# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LYQDBankBalance(Document):
	def validate(self):
		if self.bank_account and self.date:
			existing = frappe.db.exists(
				"LYQD Bank Balance",
				{
					"bank_account": self.bank_account,
					"date": self.date,
					"name": ("!=", self.name or ""),
				},
			)
			if existing:
				frappe.throw(
					frappe._("A LYQD bank balance already exists for {0} on {1}.").format(
						self.bank_account, self.date
					)
				)
