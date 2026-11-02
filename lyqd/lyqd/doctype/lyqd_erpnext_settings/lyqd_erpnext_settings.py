# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LYQDERPNextSettings(Document):
	def validate(self):
		if not self.enabled:
			return

		if self.source == "Other Site":
			if not (self.remote_site_url or "").strip():
				frappe.throw(frappe._("Remote Site URL is required for Other Site recommendations."))
			if not (self.remote_api_key or "").strip():
				frappe.throw(frappe._("API Key is required for Other Site recommendations."))
			# Secret may already be stored; only require on first enable
			has_secret = bool(self.get_password("remote_api_secret", raise_exception=False))
			if not has_secret and not self.remote_api_secret:
				frappe.throw(frappe._("API Secret is required for Other Site recommendations."))
			url = self.remote_site_url.strip().rstrip("/")
			if not url.startswith("http://") and not url.startswith("https://"):
				frappe.throw(frappe._("Site URL must start with http:// or https://"))
			self.remote_site_url = url
			# remote_company is optional at save — Connect / probe fills it from the remote site
			return

		# This Site — needs local ERPNext
		self.source = self.source or "This Site"
		if "erpnext" not in frappe.get_installed_apps():
			frappe.throw(
				frappe._("ERPNext must be installed on this site to use This Site recommendations.")
			)
