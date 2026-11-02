# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class LYQDInvestmentInstruction(Document):
	"""Local workflow only — external Mytra/BSE submit is stubbed."""

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amount: DF.Currency
		approved_by: DF.Link | None
		approved_on: DF.Datetime | None
		as_of: DF.Date | None
		company: DF.Link
		external_submit_message: DF.SmallText | None
		external_submit_status: DF.Literal["Not Submitted", "Blocked (PoC)", "Stubbed"]
		horizon_days: DF.Int
		naming_series: DF.Literal["LYQD-INS-.YYYY.-.#####"]
		notes: DF.SmallText | None
		proposal: DF.Link | None
		scheme: DF.Link
		scheme_isin: DF.Data | None
		scheme_label: DF.Data | None
		status: DF.Literal["Draft", "Approved", "Ready", "Cancelled"]
		surplus_run: DF.Link | None
	# end: auto-generated types

	def validate(self):
		if self.amount is not None and self.amount < 0:
			frappe.throw(frappe._("Amount cannot be negative"))

	@frappe.whitelist()
	def mark_approved(self):
		if self.status not in ("Draft", "Ready"):
			frappe.throw(frappe._("Only Draft / Ready instructions can be approved"))
		self.status = "Approved"
		self.approved_by = frappe.session.user
		self.approved_on = now_datetime()
		self.save()
		return self.name

	@frappe.whitelist()
	def mark_ready(self):
		if self.status not in ("Draft", "Approved"):
			frappe.throw(frappe._("Only Draft / Approved instructions can be marked Ready"))
		self.status = "Ready"
		self.save()
		return self.name

	@frappe.whitelist()
	def submit_to_mytra(self):
		"""PoC stub — never calls Mytra / BSE."""
		self.external_submit_status = "Blocked (PoC)"
		self.external_submit_message = (
			"Submit to Mytra / BSE is disabled in this PoC. "
			"Local workflow (Draft → Approved / Ready) is available; execution stays on Mytra."
		)
		self.save()
		frappe.msgprint(
			self.external_submit_message,
			title=frappe._("Execution not available"),
			indicator="orange",
		)
		return {
			"ok": False,
			"status": self.external_submit_status,
			"message": self.external_submit_message,
		}
