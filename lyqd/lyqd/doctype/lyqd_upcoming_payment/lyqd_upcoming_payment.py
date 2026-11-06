# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt


class LYQDUpcomingPayment(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from lyqd.lyqd.doctype.lyqd_upcoming_split.lyqd_upcoming_split import LYQDUpcomingSplit

		amount: DF.Currency
		balance_as_of: DF.Date | None
		cash_effect: DF.Literal["Outflow", "Setoff", "Inflow"]
		group_net: DF.Currency | None
		probability: DF.Percent | None
		category: DF.Literal[
			"Salary",
			"Import-LC",
			"Vendor",
			"Customer",
			"Tax",
			"Loan",
			"FD Maturity",
			"Loan Proceeds",
			"Other",
		]
		company: DF.Link
		due_date: DF.Date
		frequency: DF.Literal["Weekly", "Monthly", "Quarterly"] | None
		is_recurring: DF.Check
		last_synced_on: DF.Datetime | None
		naming_series: DF.Literal["LYQD-UP-.YYYY.-.#####"]
		notes: DF.SmallText | None
		parent_payment: DF.Link | None
		recurrence_end: DF.Date | None
		source_account: DF.Data | None
		source_doctype: DF.Data | None
		source_name: DF.Data | None
		source_row: DF.Data | None
		splits: DF.Table[LYQDUpcomingSplit]
		status: DF.Literal["Planned", "Paid", "Cancelled", "Ignored"]
		title: DF.Data
	# end: auto-generated types

	def validate(self):
		if self.amount is not None and self.amount < 0:
			frappe.throw(frappe._("Amount cannot be negative"))
		if not self.cash_effect:
			self.cash_effect = "Outflow"
		# Incoming (Inflow / Setoff) carries collection probability for expected cash.
		if self.cash_effect in ("Inflow", "Setoff"):
			if self.probability is None or self.probability == "":
				self.probability = 100
			self.probability = min(max(flt(self.probability), 0), 100)
		else:
			self.probability = 100
		# Per-installment probability on the GL split schedule (defaults to header).
		for split in self.get("splits") or []:
			if self.cash_effect in ("Inflow", "Setoff"):
				if split.probability is None or split.probability == "":
					split.probability = self.probability
				split.probability = min(max(flt(split.probability), 0), 100)
			else:
				split.probability = 100
		if cint(self.is_recurring):
			if self.cash_effect != "Outflow":
				frappe.throw(frappe._("Recurring series is only supported for Outflow payments."))
			if self.parent_payment:
				frappe.throw(frappe._("Nested plan rows cannot be recurring."))
			if self.get("splits"):
				frappe.throw(frappe._("GL split schedules cannot be recurring — clear Splits first."))
			if not self.frequency:
				self.frequency = "Monthly"
			if self.frequency not in ("Weekly", "Monthly", "Quarterly"):
				frappe.throw(frappe._("Invalid recurrence frequency."))
			if self.recurrence_end and self.due_date and self.recurrence_end < self.due_date:
				frappe.throw(frappe._("Repeat Until cannot be before the next due date."))
		else:
			self.frequency = None
			self.recurrence_end = None

		# Block unlinking from a parent that still has a split schedule
		if not self.is_new() and self.has_value_changed("parent_payment"):
			prev_parent = self.get_db_value("parent_payment")
			if prev_parent and not self.parent_payment:
				from lyqd.recommendations.core import _assert_can_unlink_from_parent

				_assert_can_unlink_from_parent(self.name, prev_parent)

		if self.parent_payment:
			if self.parent_payment == self.name:
				frappe.throw(frappe._("Payment cannot be its own parent."))
			parent = frappe.db.get_value(
				"LYQD Upcoming Payment",
				self.parent_payment,
				["company", "parent_payment", "due_date", "balance_as_of"],
				as_dict=True,
			)
			if not parent:
				frappe.throw(frappe._("Parent payment {0} not found.").format(self.parent_payment))
			if parent.company != self.company:
				frappe.throw(frappe._("Parent payment must belong to the same company."))
			if parent.parent_payment:
				frappe.throw(frappe._("Only one level of plan nesting is allowed."))
			if parent.due_date:
				self.due_date = parent.due_date
			if parent.balance_as_of:
				self.balance_as_of = parent.balance_as_of

		self._sync_from_splits()

	def _sync_from_splits(self):
		"""Keep header amount / due / status aligned with the GL split schedule table."""
		rows = [r for r in (self.get("splits") or []) if flt(r.amount) > 0.01]
		if not rows:
			return
		for r in rows:
			if not r.status:
				r.status = "Planned"
			if flt(r.amount) < 0:
				frappe.throw(frappe._("Split amounts cannot be negative"))
		planned = [r for r in rows if (r.status or "Planned") == "Planned"]
		self.amount = flt(sum(flt(r.amount) for r in planned), 2)
		if planned:
			earliest = min(planned, key=lambda r: str(r.due_date or "9999-99-99"))
			if earliest.due_date:
				self.due_date = earliest.due_date
			self.status = "Planned"
		else:
			# All split lines Paid
			self.amount = flt(sum(flt(r.amount) for r in rows), 2)
			self.status = "Paid"
			latest = max(rows, key=lambda r: str(r.due_date or ""))
			if latest.due_date:
				self.due_date = latest.due_date

	def on_update(self):
		from lyqd.recommendations.core import refresh_upcoming_group_net

		# Cascade due / freeze to nest children (parent is source of truth for those).
		if not self.parent_payment:
			children = frappe.get_all(
				"LYQD Upcoming Payment",
				filters={
					"parent_payment": self.name,
					"status": "Planned",
				},
				pluck="name",
			)
			if children:
				if self.has_value_changed("due_date") and self.due_date:
					for child_name in children:
						frappe.db.set_value(
							"LYQD Upcoming Payment",
							child_name,
							"due_date",
							self.due_date,
							update_modified=True,
						)
				if self.has_value_changed("balance_as_of"):
					for child_name in children:
						frappe.db.set_value(
							"LYQD Upcoming Payment",
							child_name,
							"balance_as_of",
							self.balance_as_of,
							update_modified=True,
						)

		# Keep stored nest total on the root(s) this row affects.
		prev = self.get_doc_before_save()
		prev_parent = prev.parent_payment if prev else None
		if self.parent_payment:
			refresh_upcoming_group_net(self.parent_payment)
			# Nested rows never store group_net themselves
			if flt(self.group_net):
				frappe.db.set_value(
					"LYQD Upcoming Payment",
					self.name,
					"group_net",
					0,
					update_modified=False,
				)
		else:
			refresh_upcoming_group_net(self.name)
		if prev_parent and prev_parent != self.parent_payment:
			refresh_upcoming_group_net(prev_parent)

	def after_insert(self):
		from lyqd.recommendations.core import refresh_upcoming_group_net

		if self.parent_payment:
			refresh_upcoming_group_net(self.parent_payment)
			if flt(self.group_net):
				frappe.db.set_value(
					"LYQD Upcoming Payment",
					self.name,
					"group_net",
					0,
					update_modified=False,
				)
		else:
			refresh_upcoming_group_net(self.name)

	def on_trash(self):
		from lyqd.recommendations.core import refresh_upcoming_group_net

		if self.parent_payment:
			refresh_upcoming_group_net(self.parent_payment)
		else:
			# Children may remain briefly; zero this root's stored net
			frappe.db.set_value(
				"LYQD Upcoming Payment",
				self.name,
				"group_net",
				0,
				update_modified=False,
			)
