"""
Optional soft-launch portfolio bridge: sample LYQD Investment Instructions
that match Mytra SAMPLE transaction refs in ``lyqd.mytra.portfolio``.

Usage:
  bench --site <site> execute lyqd.setup.seed_portfolio_demo.seed_portfolio_demo
  bench --site <site> execute lyqd.setup.seed_portfolio_demo.seed_portfolio_demo --kwargs "{'company': 'pwctech'}"
"""

from __future__ import annotations

import frappe
from frappe.utils import getdate, now_datetime, today


SCHEME = "ICICI Prudential Liquid Fund - Direct Growth"
ISIN = "INF109K01VQ1"


def seed_portfolio_demo(company: str | None = None) -> dict:
	"""Ensure investment account is activated and seed 1–2 instruction bridge rows."""
	company = (company or "").strip() or _default_company()
	if not company:
		frappe.throw(frappe._("Pass company= or set a default Company."))

	settings = frappe.get_single("LYQD Settings")
	settings.investment_account_activated = 1
	settings.save(ignore_permissions=True)

	created = []
	specs = [
		{
			"ref": "UT-SSA-00042",
			"amount": 500_000.0,
			"status": "Ready",
			"external": "Allotted",
			"as_of": "2026-10-27",
			"notes": "SAMPLE bridge — allotted purchase on Mytra",
		},
		{
			"ref": "UT-SSA-00058",
			"amount": 200_000.0,
			"status": "Approved",
			"external": "Submitted",
			"as_of": today(),
			"notes": "SAMPLE bridge — in-flight purchase on Mytra",
		},
	]

	for spec in specs:
		existing = frappe.db.exists(
			"LYQD Investment Instruction",
			{"company": company, "mytra_transaction_ref": spec["ref"]},
		)
		if existing:
			created.append({"name": existing, "skipped": True, "ref": spec["ref"]})
			continue

		doc = frappe.get_doc(
			{
				"doctype": "LYQD Investment Instruction",
				"company": company,
				"status": spec["status"],
				"scheme": ISIN,
				"scheme_isin": ISIN,
				"scheme_label": SCHEME,
				"amount": spec["amount"],
				"as_of": getdate(spec["as_of"]),
				"horizon_days": 7,
				"notes": spec["notes"],
				"approved_by": frappe.session.user if spec["status"] in ("Approved", "Ready") else None,
				"approved_on": now_datetime() if spec["status"] in ("Approved", "Ready") else None,
			}
		)
		doc.insert(ignore_permissions=True)
		# read_only execution fields — set after insert
		doc.db_set("external_submit_status", spec["external"], update_modified=False)
		doc.db_set("mytra_transaction_ref", spec["ref"], update_modified=False)
		doc.db_set(
			"external_submit_message",
			"SAMPLE — not submitted to live Mytra",
			update_modified=False,
		)
		created.append({"name": doc.name, "skipped": False, "ref": spec["ref"]})

	frappe.db.commit()
	return {
		"company": company,
		"investment_account_activated": 1,
		"instructions": created,
		"hint": "Open /lyqd/holdings — sample Mytra rows + these instruction bridges.",
	}


def _default_company() -> str | None:
	return frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
