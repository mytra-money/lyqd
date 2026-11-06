"""Unit tests for recurring Upcoming Payment horizon expand + next-due advance."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from frappe.tests import UnitTestCase
from frappe.utils import add_days, add_months, flt, today

from lyqd.cash.recurring import (
	advance_recurring_after_paid,
	expand_recurring_row,
	iter_occurrence_dates,
	next_due_after,
)


class TestLYQDRecurring(UnitTestCase):
	def test_next_due_frequencies(self):
		base = "2026-01-15"
		self.assertEqual(next_due_after(base, "Weekly"), "2026-01-22")
		self.assertEqual(next_due_after(base, "Monthly"), "2026-02-15")
		self.assertEqual(next_due_after(base, "Quarterly"), "2026-04-15")

	def test_iter_includes_overdue_next_due(self):
		as_of = "2026-03-01"
		dates = iter_occurrence_dates(
			"2026-02-15",
			"Monthly",
			as_of,
			"2026-04-30",
		)
		self.assertEqual(dates, ["2026-02-15", "2026-03-15", "2026-04-15"])

	def test_iter_respects_recurrence_end(self):
		dates = iter_occurrence_dates(
			"2026-01-01",
			"Monthly",
			"2026-01-01",
			"2026-06-30",
			recurrence_end="2026-03-01",
		)
		self.assertEqual(dates, ["2026-01-01", "2026-02-01", "2026-03-01"])

	def test_expand_multiplies_period_amount(self):
		as_of = today()
		row = {
			"amount": 10_000,
			"due_date": as_of,
			"is_recurring": 1,
			"frequency": "Monthly",
		}
		expand_recurring_row(row, as_of, horizon_days=75)
		self.assertEqual(flt(row["period_amount"]), 10_000)
		self.assertGreaterEqual(row["occurrence_count"], 2)
		self.assertEqual(flt(row["amount"]), flt(10_000 * row["occurrence_count"]))

	def test_expand_non_recurring_unchanged(self):
		as_of = today()
		row = {"amount": 5_000, "due_date": as_of, "is_recurring": 0}
		expand_recurring_row(row, as_of, 30)
		self.assertEqual(flt(row["amount"]), 5_000)
		self.assertEqual(row["occurrence_count"], 1)

	def test_advance_keeps_planned(self):
		due = today()
		payment = SimpleNamespace(
			is_recurring=1,
			frequency="Monthly",
			due_date=due,
			recurrence_end=None,
			status="Planned",
			notes="",
		)
		advance_recurring_after_paid(payment)
		self.assertEqual(payment.status, "Planned")
		self.assertEqual(str(payment.due_date), str(add_months(due, 1)))

	def test_advance_cancels_past_end(self):
		due = today()
		payment = SimpleNamespace(
			is_recurring=1,
			frequency="Monthly",
			due_date=due,
			recurrence_end=due,
			status="Planned",
			notes="",
		)
		advance_recurring_after_paid(payment)
		self.assertEqual(payment.status, "Cancelled")


class TestLYQDInflowSurplus(UnitTestCase):
	def test_inflow_excluded_from_free_cash(self):
		from lyqd.cash.surplus import compute_surplus

		as_of = today()
		result = compute_surplus(
			company="TEST",
			horizon_days=7,
			as_of=as_of,
			bank_cash=100_000,
			upcoming_payments=[
				{
					"name": "OUT",
					"title": "Vendor",
					"amount": 40_000,
					"due_date": add_days(as_of, 2),
					"category": "Vendor",
					"cash_effect": "Outflow",
				},
				{
					"name": "IN",
					"title": "FD matures",
					"amount": 25_000,
					"due_date": add_days(as_of, 3),
					"category": "FD Maturity",
					"cash_effect": "Inflow",
				},
			],
			min_liquidity_buffer=0,
			restricted_cash=0,
		)
		# Inflows do not change free cash: 100k - 40k = 60k
		self.assertEqual(result.upcoming_total, 40_000)
		self.assertEqual(result.investable_surplus, 60_000)


if __name__ == "__main__":
	unittest.main()
