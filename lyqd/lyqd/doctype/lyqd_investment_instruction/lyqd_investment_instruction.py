# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class LYQDInvestmentInstruction(Document):
	"""Local approval workflow; execution and holdings live on Mytra."""

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
		external_submit_status: DF.Literal[
			"Not Submitted", "Submitted", "Pending", "Allotted", "Failed", "Blocked"
		]
		horizon_days: DF.Int
		mytra_transaction_ref: DF.Data | None
		naming_series: DF.Literal["LYQD-INS-.YYYY.-.#####"]
		notes: DF.SmallText | None
		proposal: DF.Link | None
		scheme: DF.Data
		scheme_isin: DF.Data | None
		scheme_label: DF.Data | None
		side: DF.Literal["Purchase", "Redeem"]
		status: DF.Literal["Draft", "Approved", "Ready", "Cancelled"]
		surplus_run: DF.Link | None
	# end: auto-generated types

	def validate(self):
		if not self.side:
			self.side = "Purchase"
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
		"""
		Hand off a Ready instruction to Mytra (creates a transaction there).

		Soft launch: blocked until Mytra HTTP is wired; message explains the intended flow.
		"""
		if self.status != "Ready":
			frappe.throw(frappe._("Mark the instruction Ready before submitting to Mytra."))

		self.external_submit_status = "Blocked"
		self.external_submit_message = (
			"Mytra transaction handoff is not connected on this site yet. "
			"When live, Submit will create a transaction on Mytra, store mytra_transaction_ref, "
			"and Portfolio will show balances and history from that reference."
		)
		self.save()
		return {
			"ok": False,
			"status": self.external_submit_status,
			"mytra_transaction_ref": self.mytra_transaction_ref,
			"message": self.external_submit_message,
		}
