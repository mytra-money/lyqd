"""Whitelisted APIs for LYQD Desk number cards and surplus page."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from lyqd.cash.surplus import compute_surplus, compute_surplus_comparison, get_policy
from lyqd.setup.permissions import get_user_companies


def _default_company() -> str:
	company = frappe.defaults.get_user_default("Company")
	if company:
		return company
	companies = get_user_companies()
	if companies:
		return companies[0]
	row = frappe.get_all("Company", limit=1, pluck="name")
	if not row:
		frappe.throw(_("No Company found. Create a Company before using LYQD."))
	return row[0]


@frappe.whitelist()
def get_dashboard_metrics(company: str | None = None) -> dict:
	"""Workspace cards: bank cash, upcoming 7d, buffer, investable surplus."""
	company = company or _default_company()
	comparison = compute_surplus_comparison(company, horizons=[7, 30])
	run_7 = comparison["runs"]["7"]
	policy = get_policy(company)
	return {
		"company": company,
		"bank_cash": run_7["bank_cash"],
		"upcoming_7d": run_7["upcoming_total"],
		"min_liquidity_buffer": flt(policy.get("min_liquidity_buffer")),
		"restricted_cash": flt(policy.get("restricted_cash")),
		"investable_surplus_7d": run_7["investable_surplus"],
		"is_shortfall_7d": run_7["is_shortfall"],
		"comparison": comparison,
		"display_scheme_label": frappe.db.get_single_value("LYQD Settings", "display_scheme_label"),
	}


@frappe.whitelist()
def get_surplus_explanation(
	company: str | None = None,
	horizon_days: int | str = 7,
) -> dict:
	from lyqd.cash.surplus import parse_horizon_days

	company = company or _default_company()
	result = compute_surplus(company, horizon_days=parse_horizon_days(horizon_days))
	return result.as_dict()


@frappe.whitelist()
def save_surplus_run(
	company: str | None = None,
	horizon_days: int | str = 7,
) -> str:
	"""Persist a Surplus Run for demos / audit trail."""
	from lyqd.cash.surplus import parse_horizon_days

	company = company or _default_company()
	result = compute_surplus(company, horizon_days=parse_horizon_days(horizon_days))
	doc = frappe.get_doc(
		{
			"doctype": "LYQD Surplus Run",
			"company": company,
			"as_of": result.as_of,
			"horizon_days": result.horizon_days,
			"horizon_end": result.horizon_end,
			"bank_cash": result.bank_cash,
			"upcoming_total": result.upcoming_total,
			"min_liquidity_buffer": result.min_liquidity_buffer,
			"restricted_cash": result.restricted_cash,
			"investable_surplus": result.investable_surplus,
			"is_shortfall": 1 if result.is_shortfall else 0,
			"policy": result.policy_name,
			"explanation_json": frappe.as_json(result.as_dict()),
			"lines": [
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
				}
				for line in result.explanation
			],
		}
	)
	doc.insert()
	return doc.name


# --- Number Card custom methods ---


@frappe.whitelist()
def number_card_bank_cash() -> float:
	return flt(get_dashboard_metrics()["bank_cash"])


@frappe.whitelist()
def number_card_upcoming_7d() -> float:
	return flt(get_dashboard_metrics()["upcoming_7d"])


@frappe.whitelist()
def number_card_liquidity_buffer() -> float:
	return flt(get_dashboard_metrics()["min_liquidity_buffer"])


@frappe.whitelist()
def number_card_investable_surplus() -> float:
	return flt(get_dashboard_metrics()["investable_surplus_7d"])
