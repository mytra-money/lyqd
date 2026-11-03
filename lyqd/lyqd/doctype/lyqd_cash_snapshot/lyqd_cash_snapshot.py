# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LYQDCashSnapshot(Document):
	def validate(self):
		ba = frappe.db.get_value(
			"LYQD Bank Account",
			self.bank_account,
			["company", "is_active", "account_name"],
			as_dict=True,
		)
		if not ba:
			frappe.throw(frappe._("LYQD Bank Account not found"))
		if not ba.is_active:
			frappe.throw(frappe._("Bank Account is inactive"))
		if ba.company and self.company and ba.company != self.company:
			frappe.throw(frappe._("Bank Account company must match Snapshot company"))
		if not self.company:
			self.company = ba.company
		self.gl_account = None

	def after_insert(self):
		self._sync_lyqd_bank_balance()

	def on_update(self):
		self._sync_lyqd_bank_balance()

	def _sync_lyqd_bank_balance(self):
		from lyqd.cash.bank_cash import set_statement_balance

		set_statement_balance(self.bank_account, self.balance, self.as_on)
		if hasattr(self, "synced_to_bank_account_balance"):
			frappe.db.set_value(
				self.doctype,
				self.name,
				"synced_to_bank_account_balance",
				1,
				update_modified=False,
			)
