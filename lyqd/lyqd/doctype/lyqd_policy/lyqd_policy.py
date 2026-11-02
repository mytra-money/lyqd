# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LYQDPolicy(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		company: DF.Link
		default_forecast_horizon_days: DF.Int
		is_active: DF.Check
		min_liquidity_buffer: DF.Currency
		notes: DF.SmallText | None
		restricted_cash: DF.Currency
	# end: auto-generated types

	def validate(self):
		if self.default_forecast_horizon_days is not None and self.default_forecast_horizon_days < 0:
			frappe.throw(frappe._("Forecast horizon cannot be negative"))
		if self.min_liquidity_buffer is not None and self.min_liquidity_buffer < 0:
			frappe.throw(frappe._("Minimum liquidity buffer cannot be negative"))
		if self.restricted_cash is not None and self.restricted_cash < 0:
			frappe.throw(frappe._("Restricted cash cannot be negative"))
