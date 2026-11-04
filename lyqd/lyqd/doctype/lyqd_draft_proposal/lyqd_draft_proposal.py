# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class LYQDDraftProposal(Document):
	"""Invest or Redeem request frozen from a Surplus Run — no Mytra / BSE submit here."""

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
		request_type: DF.Literal["Invest", "Redeem"]
		restricted_cash: DF.Currency
		status: DF.Literal["Draft", "Frozen", "Cancelled"]
		surplus_run: DF.Link
		upcoming_total: DF.Currency
	# end: auto-generated types

	def validate(self):
		if not self.request_type:
			self.request_type = "Invest"
		if self.status != "Cancelled" and not self.surplus_run:
			frappe.throw(frappe._("Surplus Run is required on the request."))
		if self.status != "Cancelled" and flt(self.proposed_amount) <= 0:
			frappe.throw(
				frappe._(
					"Proposed amount must be greater than zero. "
					"There is no free cash to invest / nothing to redeem."
				)
			)
		if self.surplus_run and self.status != "Cancelled":
			is_shortfall = frappe.db.get_value("LYQD Surplus Run", self.surplus_run, "is_shortfall")
			if self.request_type == "Invest" and is_shortfall:
				frappe.throw(frappe._("Invest requests cannot use a shortfall Surplus Run."))
			if self.request_type == "Redeem" and not is_shortfall:
				frappe.throw(frappe._("Redeem requests require a shortfall Surplus Run."))

	def apply_surplus_run(self, run=None, *, proposed_amount: float | None = None):
		"""Copy frozen numbers from the linked Surplus Run onto this proposal."""
		run = run or frappe.get_doc("LYQD Surplus Run", self.surplus_run)
		request_type = self.request_type or "Invest"
		if request_type == "Invest" and run.is_shortfall:
			frappe.throw(frappe._("Cannot use a shortfall Surplus Run for an investment request."))
		if request_type == "Redeem" and not run.is_shortfall:
			frappe.throw(frappe._("Redeem requests require a shortfall Surplus Run."))

		settings = frappe.get_single("LYQD Settings")
		self.as_of = run.as_of
		self.horizon_days = run.horizon_days
		self.bank_cash = run.bank_cash
		self.upcoming_total = run.upcoming_total
		self.min_liquidity_buffer = run.min_liquidity_buffer
		self.restricted_cash = run.restricted_cash
		if proposed_amount is not None:
			self.proposed_amount = flt(proposed_amount)
		elif request_type == "Redeem":
			self.proposed_amount = abs(flt(run.investable_surplus))
		else:
			self.proposed_amount = run.investable_surplus
		if not self.display_scheme_label:
			self.display_scheme_label = settings.display_scheme_label
		if not self.display_scheme_isin:
			self.display_scheme_isin = settings.display_scheme_isin
		self.frozen_explanation = run.explanation_json
		return self

	@frappe.whitelist()
	def freeze_from_surplus(self):
		"""Confirm the request from its Surplus Run (create a run if missing — legacy Desk)."""
		if not self.surplus_run:
			from lyqd.api.dashboard import create_surplus_run_doc

			run = create_surplus_run_doc(
				company=self.company,
				horizon_days=self.horizon_days,
				as_of=self.as_of,
			)
			self.surplus_run = run.name
			self.apply_surplus_run(run)
		else:
			self.apply_surplus_run()
		self.status = "Frozen"
		self.save()
		return self.name
