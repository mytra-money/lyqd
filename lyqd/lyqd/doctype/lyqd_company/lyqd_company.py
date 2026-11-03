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

		self.books_source = self.books_source or "Manual"
		if self.books_source == "Manual":
			return

		if not (self.books_company or "").strip():
			self.books_company = self.company_name

		if self.books_source == "This Site":
			if "erpnext" not in frappe.get_installed_apps():
				frappe.throw(
					frappe._(
						"ERPNext must be installed on this site to use This Site books for {0}."
					).format(self.company_name)
				)
			return

		if self.books_source == "Other Site":
			if not (self.remote_site_url or "").strip():
				frappe.throw(frappe._("Remote Site URL is required for Other Site books."))
			if not (self.remote_api_key or "").strip():
				frappe.throw(frappe._("API Key is required for Other Site books."))
			has_secret = bool(self.get_password("remote_api_secret", raise_exception=False))
			if not has_secret and not self.remote_api_secret:
				frappe.throw(frappe._("API Secret is required for Other Site books."))
			url = self.remote_site_url.strip().rstrip("/")
			if not url.startswith("http://") and not url.startswith("https://"):
				frappe.throw(frappe._("Site URL must start with http:// or https://"))
			self.remote_site_url = url
