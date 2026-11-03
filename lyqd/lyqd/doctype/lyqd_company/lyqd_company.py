# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class LYQDCompany(Document):
	def validate(self):
		self.company_name = (self.company_name or "").strip()
		if not self.company_name:
			frappe.throw(frappe._("Company Name is required"))
		if not self.abbr:
			parts = self.company_name.split()
			self.abbr = "".join(p[0] for p in parts[:3]).upper() or self.company_name[:3].upper()

		self._validate_books()
		self._validate_policy()

	def _validate_books(self):
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

	def _validate_policy(self):
		if self.default_forecast_horizon_days is None:
			self.default_forecast_horizon_days = 7
		if self.default_forecast_horizon_days < 0:
			frappe.throw(frappe._("Forecast horizon cannot be negative"))
		if self.min_liquidity_buffer is not None and flt(self.min_liquidity_buffer) < 0:
			frappe.throw(frappe._("Minimum liquidity buffer cannot be negative"))
		if self.restricted_cash is not None and flt(self.restricted_cash) < 0:
			frappe.throw(frappe._("Restricted cash cannot be negative"))

	def apply_settings_defaults(self):
		"""Fill blank policy scalars from LYQD Settings."""
		if not frappe.db.exists("DocType", "LYQD Settings"):
			return
		settings = frappe.get_single("LYQD Settings")
		if self.min_liquidity_buffer is None:
			self.min_liquidity_buffer = flt(settings.default_min_liquidity_buffer)
		if self.restricted_cash is None:
			self.restricted_cash = flt(settings.default_restricted_cash)
		if not self.default_forecast_horizon_days:
			self.default_forecast_horizon_days = int(settings.default_forecast_horizon_days or 7)

	def before_insert(self):
		self.apply_settings_defaults()
