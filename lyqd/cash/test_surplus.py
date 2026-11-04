"""Unit tests for LYQD investable surplus formula."""

from __future__ import annotations

import unittest

from frappe.tests import UnitTestCase
from frappe.utils import add_days, flt, getdate, today

from lyqd.cash.surplus import compute_surplus


class TestLYQDSurplusFormula(UnitTestCase):
	"""Formula-only tests — no DocType fixtures required."""

	def test_basic_surplus(self):
		as_of = today()
		result = compute_surplus(
			company="TEST",
			horizon_days=7,
			as_of=as_of,
			bank_cash=4_80_00_000,
			upcoming_payments=[
				{
					"name": "UP-GST",
					"title": "GST",
					"amount": 15_00_000,
					"due_date": add_days(as_of, 5),
					"category": "Tax",
				}
			],
			min_liquidity_buffer=50_00_000,
			restricted_cash=0,
		)
		# 4.8Cr - 0.15Cr - 0.5Cr = 4.15Cr
		self.assertEqual(result.investable_surplus, 4_15_00_000)
		self.assertFalse(result.is_shortfall)
		self.assertEqual(result.upcoming_total, 15_00_000)

	def test_only_planned_in_horizon_count(self):
		"""Caller supplies already-filtered Planned+horizon rows; Paid must not be included by caller.
		Here we assert the formula sums only what it is given — Paid should simply not be passed.
		"""
		as_of = today()
		result = compute_surplus(
			company="TEST",
			horizon_days=7,
			as_of=as_of,
			bank_cash=100,
			upcoming_payments=[
				{"name": "A", "amount": 10, "due_date": as_of, "category": "Tax", "title": "A"},
			],
			min_liquidity_buffer=0,
			restricted_cash=0,
		)
		self.assertEqual(result.investable_surplus, 90)

	def test_7d_vs_30d_demo_shape(self):
		as_of = getdate(today())
		payments_7 = [
			{
				"name": "GST",
				"title": "GST",
				"amount": 15_00_000,
				"due_date": add_days(as_of, 5),
				"category": "Tax",
			}
		]
		payments_30 = payments_7 + [
			{
				"name": "LC",
				"title": "LC",
				"amount": 80_00_000,
				"due_date": add_days(as_of, 12),
				"category": "Import-LC",
			},
			{
				"name": "SAL",
				"title": "Salary",
				"amount": 1_20_00_000,
				"due_date": add_days(as_of, 28),
				"category": "Salary",
			},
		]
		s7 = compute_surplus(
			company="TEST",
			horizon_days=7,
			as_of=as_of,
			bank_cash=4_80_00_000,
			upcoming_payments=payments_7,
			min_liquidity_buffer=50_00_000,
			restricted_cash=0,
		)
		s30 = compute_surplus(
			company="TEST",
			horizon_days=30,
			as_of=as_of,
			bank_cash=4_80_00_000,
			upcoming_payments=payments_30,
			min_liquidity_buffer=50_00_000,
			restricted_cash=0,
		)
		self.assertEqual(s7.upcoming_total, 15_00_000)
		self.assertEqual(s30.upcoming_total, 2_15_00_000)
		self.assertGreater(s7.investable_surplus, s30.investable_surplus)
		# 4.8Cr - 0.15Cr - 0.5Cr = 4.15Cr
		self.assertEqual(s7.investable_surplus, 4_15_00_000)
		# 4.8Cr - 2.15Cr - 0.5Cr = 2.15Cr
		self.assertEqual(s30.investable_surplus, 2_15_00_000)

	def test_shortfall_not_invented(self):
		result = compute_surplus(
			company="TEST",
			horizon_days=7,
			as_of=today(),
			bank_cash=10,
			upcoming_payments=[{"name": "X", "amount": 50, "due_date": today(), "title": "X"}],
			min_liquidity_buffer=20,
			restricted_cash=5,
		)
		self.assertEqual(result.investable_surplus, -65)
		self.assertTrue(result.is_shortfall)
		total_line = result.explanation[-1]
		self.assertEqual(total_line.kind, "total")
		self.assertEqual(total_line.sign, "shortfall")
		self.assertEqual(total_line.amount, 65)

	def test_restricted_and_buffer_subtract(self):
		result = compute_surplus(
			company="TEST",
			horizon_days=7,
			as_of=today(),
			bank_cash=1000,
			upcoming_payments=[],
			min_liquidity_buffer=100,
			restricted_cash=200,
		)
		self.assertEqual(result.investable_surplus, 700)
		kinds = [e.kind for e in result.explanation]
		self.assertIn("buffer", kinds)
		self.assertIn("restricted", kinds)

	def test_explanation_lists_upcoming(self):
		as_of = today()
		result = compute_surplus(
			company="TEST",
			horizon_days=7,
			as_of=as_of,
			bank_cash=1000,
			upcoming_payments=[
				{
					"name": "UP-1",
					"title": "Vendor bill",
					"amount": 250,
					"due_date": as_of,
					"category": "Vendor",
				}
			],
			min_liquidity_buffer=0,
			restricted_cash=0,
		)
		upcoming_lines = [e for e in result.explanation if e.kind == "upcoming"]
		self.assertEqual(len(upcoming_lines), 1)
		self.assertEqual(upcoming_lines[0].ref_name, "UP-1")
		self.assertEqual(upcoming_lines[0].category, "Vendor")
		self.assertEqual(flt(upcoming_lines[0].amount), 250)

	def test_explanation_nests_parent_payment_groups(self):
		as_of = today()
		result = compute_surplus(
			company="TEST",
			horizon_days=7,
			as_of=as_of,
			bank_cash=100_000,
			upcoming_payments=[
				{
					"name": "P-IGST",
					"title": "Output Tax IGST",
					"amount": 10_000,
					"due_date": as_of,
					"category": "Tax",
					"cash_effect": "Outflow",
				},
				{
					"name": "C-CGST",
					"title": "Output Tax CGST",
					"amount": 5_000,
					"due_date": as_of,
					"category": "Tax",
					"cash_effect": "Outflow",
					"parent_payment": "P-IGST",
				},
				{
					"name": "C-ITC",
					"title": "Input Tax IGST",
					"amount": 2_000,
					"due_date": as_of,
					"category": "Tax",
					"cash_effect": "Setoff",
					"parent_payment": "P-IGST",
				},
			],
			min_liquidity_buffer=0,
			restricted_cash=0,
		)
		# Net reserved = 10000 + 5000 - 2000 = 13000
		self.assertEqual(result.upcoming_total, 13_000)
		upcoming_lines = [e for e in result.explanation if e.kind == "upcoming"]
		self.assertEqual(len(upcoming_lines), 1)
		parent = upcoming_lines[0]
		self.assertEqual(parent.ref_name, "P-IGST")
		self.assertEqual(parent.child_count, 2)
		self.assertEqual(flt(parent.amount), 13_000)
		self.assertEqual(parent.sign, "-")
		self.assertEqual(flt(parent.gl_amount), 10_000)
		self.assertEqual(len(parent.children), 2)
		self.assertEqual(parent.children[0].ref_name, "C-CGST")
		self.assertEqual(parent.children[1].ref_name, "C-ITC")
		self.assertEqual(parent.children[1].sign, "+")


	def test_overdue_planned_still_reserves(self):
		"""Overdue Planned rows must reduce surplus (passed through as upcoming_payments)."""
		as_of = today()
		result = compute_surplus(
			company="TEST",
			horizon_days=7,
			as_of=as_of,
			bank_cash=1000,
			upcoming_payments=[
				{
					"name": "OVERDUE",
					"title": "Late vendor",
					"amount": 200,
					"due_date": add_days(as_of, -3),
					"category": "Vendor",
				},
				{
					"name": "FUTURE",
					"title": "Next week",
					"amount": 100,
					"due_date": add_days(as_of, 5),
					"category": "Tax",
				},
			],
			min_liquidity_buffer=0,
			restricted_cash=0,
		)
		self.assertEqual(result.upcoming_total, 300)
		self.assertEqual(result.investable_surplus, 700)
		overdue_line = next(e for e in result.explanation if e.ref_name == "OVERDUE")
		self.assertIn("overdue", overdue_line.label.lower())


# Allow `python -m unittest` style discovery without FrappeTestCase DB if needed
class TestLYQDSurplusPure(unittest.TestCase):
	def test_zero_cash_shortfall(self):
		result = compute_surplus(
			company="TEST",
			horizon_days=7,
			as_of=today(),
			bank_cash=0,
			upcoming_payments=[{"name": "Y", "amount": 1, "due_date": today(), "title": "Y"}],
			min_liquidity_buffer=0,
			restricted_cash=0,
		)
		self.assertTrue(result.is_shortfall)
		self.assertEqual(result.investable_surplus, -1)
