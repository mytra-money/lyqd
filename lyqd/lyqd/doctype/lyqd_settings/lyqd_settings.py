# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LYQDSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		default_forecast_horizon_days: DF.Int
		default_min_liquidity_buffer: DF.Currency
		default_restricted_cash: DF.Currency
		display_scheme_isin: DF.Data | None
		display_scheme_label: DF.Data | None
		enable_draft_proposals: DF.Check
		erpnext_integration_enabled: DF.Check
		erpnext_source: DF.Literal["This Site", "Other Site"]
		investment_account_activated: DF.Check
		investment_account_crm_lead: DF.Data | None
		investment_account_requested_on: DF.Datetime | None
		remote_api_key: DF.Data | None
		remote_api_secret: DF.Password | None
		remote_company: DF.Data | None
		remote_site_url: DF.Data | None
		tagline: DF.Data | None
	# end: auto-generated types

	def validate(self):
		if not self.erpnext_integration_enabled:
			return

		source = self.erpnext_source or "This Site"
		self.erpnext_source = source

		if source == "Other Site":
			if not (self.remote_site_url or "").strip():
				frappe.throw(frappe._("Remote Site URL is required for Other Site recommendations."))
			if not (self.remote_api_key or "").strip():
				frappe.throw(frappe._("API Key is required for Other Site recommendations."))
			has_secret = bool(self.get_password("remote_api_secret", raise_exception=False))
			if not has_secret and not self.remote_api_secret:
				frappe.throw(frappe._("API Secret is required for Other Site recommendations."))
			url = self.remote_site_url.strip().rstrip("/")
			if not url.startswith("http://") and not url.startswith("https://"):
				frappe.throw(frappe._("Site URL must start with http:// or https://"))
			self.remote_site_url = url
			return

		if "erpnext" not in frappe.get_installed_apps():
			frappe.throw(
				frappe._(
					"ERPNext must be installed on this site to use This Site books. "
					"Or switch to Other Site / leave recommendations off."
				)
			)
