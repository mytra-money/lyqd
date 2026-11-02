# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LYQDCashSnapshot(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		as_on: DF.Date
		balance: DF.Currency
		bank_account: DF.Link
		company: DF.Link
		gl_account: DF.Link | None
		naming_series: DF.Literal["LYQD-CASH-.YYYY.-.#####"]
		notes: DF.SmallText | None
		synced_to_bank_account_balance: DF.Check
	# end: auto-generated types

	def validate(self):
		ba = frappe.db.get_value(
			"Bank Account",
			self.bank_account,
			["company", "is_company_account", "account", "disabled"],
			as_dict=True,
		)
		if not ba:
			frappe.throw(frappe._("Bank Account not found"))
		if ba.disabled:
			frappe.throw(frappe._("Bank Account is disabled"))
		if not ba.is_company_account:
			frappe.throw(frappe._("Only company bank accounts can be used for LYQD cash"))
		if ba.company and self.company and ba.company != self.company:
			frappe.throw(frappe._("Bank Account company must match Snapshot company"))
		if not self.company:
			self.company = ba.company
		self.gl_account = ba.account

	def after_insert(self):
		self._sync_bank_account_balance()

	def on_update(self):
		self._sync_bank_account_balance()

	def _sync_bank_account_balance(self):
		"""When ERPNext Bank Account Balance exists, keep it as the ledger-side figure."""
		if not frappe.db.exists("DocType", "Bank Account Balance"):
			return

		existing = frappe.db.exists(
			"Bank Account Balance",
			{"bank_account": self.bank_account, "date": self.as_on},
		)
		if existing:
			doc = frappe.get_doc("Bank Account Balance", existing)
			doc.balance = self.balance
			doc.flags.ignore_permissions = True
			doc.save()
		else:
			doc = frappe.get_doc(
				{
					"doctype": "Bank Account Balance",
					"bank_account": self.bank_account,
					"date": self.as_on,
					"balance": self.balance,
				}
			)
			doc.flags.ignore_permissions = True
			doc.insert()

		frappe.db.set_value(
			self.doctype,
			self.name,
			"synced_to_bank_account_balance",
			1,
			update_modified=False,
		)
