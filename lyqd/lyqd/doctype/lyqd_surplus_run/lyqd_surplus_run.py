# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from lyqd.cash.surplus import compute_surplus


class LYQDSurplusRun(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from lyqd.lyqd.doctype.lyqd_surplus_run_line.lyqd_surplus_run_line import LYQDSurplusRunLine

		as_of: DF.Date
		bank_cash: DF.Currency
		company: DF.Link
		explanation_json: DF.Code | None
		horizon_days: DF.Int
		horizon_end: DF.Date | None
		investable_surplus: DF.Currency
		is_shortfall: DF.Check
		lines: DF.Table[LYQDSurplusRunLine]
		min_liquidity_buffer: DF.Currency
		naming_series: DF.Literal["LYQD-SR-.YYYY.-.#####"]
		policy: DF.Link | None
		restricted_cash: DF.Currency
		upcoming_total: DF.Currency
	# end: auto-generated types

	@frappe.whitelist()
	def recalculate(self):
		result = compute_surplus(self.company, horizon_days=self.horizon_days, as_of=self.as_of)
		self.horizon_end = result.horizon_end
		self.bank_cash = result.bank_cash
		self.upcoming_total = result.upcoming_total
		self.min_liquidity_buffer = result.min_liquidity_buffer
		self.restricted_cash = result.restricted_cash
		self.investable_surplus = result.investable_surplus
		self.is_shortfall = 1 if result.is_shortfall else 0
		self.policy = result.policy_name
		self.explanation_json = frappe.as_json(result.as_dict())
		self.set("lines", [])
		for line in result.explanation:
			self.append(
				"lines",
				{
					"kind": line.kind,
					"label": line.label,
					"amount": line.amount,
					"sign": line.sign,
					"ref_doctype": line.ref_doctype,
					"ref_name": line.ref_name,
					"due_date": line.due_date,
					"category": line.category,
					"notes": line.notes,
				},
			)
		return self
