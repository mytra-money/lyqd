# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class LYQDCompany(Document):
	def onload(self):
		self._sync_checks_from_books_source()

	def before_validate(self):
		# CRM-style checks are the UI source of truth; books_source is derived.
		self._sync_books_source_from_checks()

	def validate(self):
		self.company_name = (self.company_name or "").strip()
		if not self.company_name:
			frappe.throw(frappe._("Company Name is required"))
		if not self.abbr:
			parts = self.company_name.split()
			self.abbr = "".join(p[0] for p in parts[:3]).upper() or self.company_name[:3].upper()

		self._validate_books()
		self._validate_policy()
		self._validate_recommendation_accounts()

	def _validate_recommendation_accounts(self):
		"""Top Bar–style: refs-off parents only; one-level children; no cycles."""
		rows = self.get("recommendation_accounts") or []
		by_account = {}
		for row in rows:
			acc = (row.account or "").strip()
			if not acc:
				continue
			if acc in by_account:
				frappe.throw(frappe._("Duplicate recommendation account: {0}").format(acc))
			by_account[acc] = row

		for row in rows:
			acc = (row.account or "").strip()
			parent = (getattr(row, "parent_account", None) or "").strip()
			if not parent:
				row.parent_account = None
				continue
			row.parent_account = parent
			if int(row.show_references or 0):
				frappe.throw(
					frappe._(
						"Account {0} has voucher references and cannot nest under a parent."
					).format(acc)
				)
			parent_row = by_account.get(parent)
			if not parent_row:
				frappe.throw(
					frappe._("Parent account {0} is not in the recommendation list.").format(parent)
				)
			if int(parent_row.show_references or 0):
				frappe.throw(
					frappe._(
						"Parent {0} must have voucher references turned off to group other accounts."
					).format(parent)
				)
			if parent == acc:
				frappe.throw(frappe._("Account {0} cannot be its own parent.").format(acc))
			# One level only: parent must not itself be a child
			grand = (getattr(parent_row, "parent_account", None) or "").strip()
			if grand:
				frappe.throw(
					frappe._(
						"Parent {0} is already nested under {1}. Only one level of grouping is allowed."
					).format(parent, grand)
				)

	def _sync_checks_from_books_source(self):
		"""Populate CRM-style checks from stored books_source (onload / API helpers)."""
		source = self.books_source or "Manual"
		self.erpnext_enabled = 1 if source in ("This Site", "Other Site") else 0
		self.is_erpnext_in_the_current_site = 1 if source == "This Site" else 0

	def _sync_books_source_from_checks(self):
		"""Derive books_source from Enable ERPNext + this-site checks."""
		if not int(self.erpnext_enabled or 0):
			self.books_source = "Manual"
			self.is_erpnext_in_the_current_site = 0
			return
		if int(self.is_erpnext_in_the_current_site or 0):
			self.books_source = "This Site"
		else:
			self.books_source = "Other Site"

	def apply_books_source(self, books_source: str):
		"""Set books_source and matching CRM-style checks (SPA / API)."""
		self.books_source = books_source or "Manual"
		self._sync_checks_from_books_source()

	def _validate_books(self):
		self.books_source = self.books_source or "Manual"

		if self.books_source == "Manual":
			return

		if self.books_source == "This Site":
			if "erpnext" not in frappe.get_installed_apps():
				frappe.throw(
					frappe._(
						"ERPNext must be installed on this site to use This Site books for {0}."
					).format(self.company_name)
				)
			books = (self.books_company or "").strip()
			if not books:
				frappe.throw(
					frappe._(
						"Books company is required for This Site. "
						"Pick the ERPNext Company whose books this LYQD Company should use."
					)
				)
			if not frappe.db.exists("Company", books):
				frappe.throw(
					frappe._("Company {0} was not found on this site.").format(books)
				)
			self.books_company = books
			return

		if self.books_source == "Other Site":
			if not (self.books_company or "").strip():
				frappe.throw(
					frappe._(
						"Books company is required for Other Site books. "
						"Pick the ERPNext Company whose books this LYQD Company should use."
					)
				)
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
