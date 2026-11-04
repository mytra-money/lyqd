"""Integration checks for morning MIS drift flags (Demo Corp live data optional)."""

from __future__ import annotations

from frappe.tests import UnitTestCase
from frappe.utils import flt

from lyqd.api.spa import get_morning_mis


class TestMorningMisDriftPure(UnitTestCase):
	"""Exercise redeem under/over/exact and invest-flip against get_morning_mis math.

	Uses monkeypatched proposal + surplus inputs via temporary DB rows only when
	LYQD Demo Corp exists; otherwise skips.
	"""

	def setUp(self):
		import frappe

		self.frappe = frappe
		self.company = "LYQD Demo Corp"
		if not frappe.db.exists("LYQD Company", self.company):
			self.skipTest("LYQD Demo Corp not installed")
		rows = frappe.get_all(
			"LYQD Draft Proposal",
			filters={"company": self.company, "status": ("in", ["Draft", "Frozen"])},
			fields=["name", "proposed_amount", "status", "request_type"],
			limit=1,
		)
		self.saved = rows[0] if rows else None
		if not self.saved:
			self.skipTest("No open Draft Proposal on Demo Corp")

	def tearDown(self):
		if getattr(self, "saved", None):
			self.frappe.db.set_value(
				"LYQD Draft Proposal",
				self.saved.name,
				{
					"status": self.saved.status,
					"proposed_amount": self.saved.proposed_amount,
					"request_type": self.saved.request_type,
				},
			)
			self.frappe.db.commit()

	def _set_open(self, amount: float, request_type: str):
		for name in self.frappe.get_all(
			"LYQD Draft Proposal",
			filters={"company": self.company, "status": ("in", ["Draft", "Frozen"])},
			pluck="name",
		):
			self.frappe.db.set_value("LYQD Draft Proposal", name, "status", "Cancelled")
		self.frappe.db.set_value(
			"LYQD Draft Proposal",
			self.saved.name,
			{
				"status": "Frozen",
				"proposed_amount": amount,
				"request_type": request_type,
			},
		)
		self.frappe.db.commit()

	def test_horizon_mis_matches_surplus(self):
		from lyqd.cash.surplus import compute_surplus

		for h in (7, 14, 30, 60):
			mis = get_morning_mis(self.company, horizon_days=h)
			sur = compute_surplus(self.company, horizon_days=h)
			self.assertAlmostEqual(flt(mis["bank_cash"]), flt(sur.bank_cash), places=2)
			self.assertAlmostEqual(flt(mis["upcoming_total"]), flt(sur.upcoming_total), places=2)
			self.assertAlmostEqual(
				flt(mis["investable_surplus"]), flt(sur.investable_surplus), places=2
			)
			self.assertEqual(bool(mis["is_shortfall"]), bool(sur.is_shortfall))
			required = (
				flt(sur.upcoming_total)
				+ flt(sur.min_liquidity_buffer)
				+ flt(sur.restricted_cash)
			)
			self.assertAlmostEqual(flt(mis["required_cash"]), required, places=2)
			cash_gap = max(0.0, required - flt(mis["bank_cash"]))
			self.assertAlmostEqual(flt(mis["cash_gap"]), cash_gap, places=2)
			if mis["is_shortfall"]:
				self.assertAlmostEqual(
					abs(flt(mis["investable_surplus"])), flt(mis["cash_gap"]), places=2
				)

	def test_redeem_under_exact_over_and_invest_flip(self):
		mis30 = get_morning_mis(self.company, 30)
		if not mis30["is_shortfall"]:
			self.skipTest("30d is not a shortfall on Demo Corp right now")
		need = flt(mis30["redemption_need"])
		self.assertGreater(need, 0)

		self._set_open(need - 7000, "Redeem")
		m = get_morning_mis(self.company, 30)
		self.assertAlmostEqual(flt(m["redeem_under_need"]), 7000, places=2)
		self.assertLess(flt(m["redeem_over_need"]), 0.01)

		self._set_open(need, "Redeem")
		m = get_morning_mis(self.company, 30)
		self.assertLess(flt(m["redeem_under_need"]), 0.01)
		self.assertLess(flt(m["redeem_over_need"]), 0.01)

		self._set_open(need + 5000, "Redeem")
		m = get_morning_mis(self.company, 30)
		self.assertAlmostEqual(flt(m["redeem_over_need"]), 5000, places=2)
		self.assertLess(flt(m["redeem_under_need"]), 0.01)

		self._set_open(10_000, "Invest")
		m = get_morning_mis(self.company, 30)
		self.assertTrue(m["invest_flipped_to_shortfall"])

	def test_redeem_stale_on_short_horizon_with_free_cash(self):
		mis7 = get_morning_mis(self.company, 7)
		if mis7["is_shortfall"]:
			self.skipTest("7d is shortfall — cannot assert redeem_no_longer_needed")
		self._set_open(50_000, "Redeem")
		m = get_morning_mis(self.company, 7)
		self.assertTrue(m["redeem_no_longer_needed"])
		self.assertLess(flt(m["redeem_under_need"]), 0.01)
		self.assertLess(flt(m["redeem_over_need"]), 0.01)

	def test_invest_over_allocated_on_free_cash_horizon(self):
		mis7 = get_morning_mis(self.company, 7)
		if mis7["is_shortfall"]:
			self.skipTest("7d is shortfall")
		free = flt(mis7["investable_surplus"])
		self._set_open(free + 5_000, "Invest")
		m = get_morning_mis(self.company, 7)
		self.assertAlmostEqual(flt(m["over_allocated"]), 5_000, places=2)
		self.assertFalse(m["invest_flipped_to_shortfall"])
