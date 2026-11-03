# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LYQDCompany(Document):
	def validate(self):
		self.company_name = (self.company_name or "").strip()
		if not self.company_name:
			frappe.throw(frappe._("Company Name is required"))
		if not self.abbr:
			parts = self.company_name.split()
			self.abbr = "".join(p[0] for p in parts[:3]).upper() or self.company_name[:3].upper()
		if self.books_source in ("This Site", "Other Site") and not (self.books_company or "").strip():
			# Default books company label to the LYQD company name
			self.books_company = self.company_name
