# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from lyqd.cash.surplus import compute_surplus


class LYQDDraftProposal(Document):
	"""Freeze surplus numbers only — no Mytra / BSE submit in this PoC."""

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		as_of: DF.Date
		bank_cash: DF.Currency
		company: DF.Link
		display_scheme_isin: DF.Data | None
		display_scheme_label: DF.Data | None
		frozen_explanation: DF.Code | None
		horizon_days: DF.Int
		min_liquidity_buffer: DF.Currency
		naming_series: DF.Literal["LYQD-PROP-.YYYY.-.#####"]
		notes: DF.SmallText | None
		proposed_amount: DF.Currency
		restricted_cash: DF.Currency
		status: DF.Literal["Draft", "Frozen", "Cancelled"]
		surplus_run: DF.Link | None
		upcoming_total: DF.Currency
	# end: auto-generated types

	def validate(self):
		if self.status == "Frozen" and (self.proposed_amount is None or self.proposed_amount < 0):
			frappe.throw(frappe._("Cannot freeze a proposal with a negative proposed amount (shortfall)"))

	@frappe.whitelist()
	def freeze_from_surplus(self):
		result = compute_surplus(self.company, horizon_days=self.horizon_days, as_of=self.as_of)
		if result.is_shortfall:
			frappe.throw(frappe._("Cannot freeze a proposal while in shortfall"))

		settings = frappe.get_single("LYQD Settings")
		self.bank_cash = result.bank_cash
		self.upcoming_total = result.upcoming_total
		self.min_liquidity_buffer = result.min_liquidity_buffer
		self.restricted_cash = result.restricted_cash
		self.proposed_amount = result.investable_surplus
		self.display_scheme_label = settings.display_scheme_label
		self.display_scheme_isin = settings.display_scheme_isin
		self.frozen_explanation = frappe.as_json(result.as_dict())
		self.status = "Frozen"
		self.save()
		return self.name
