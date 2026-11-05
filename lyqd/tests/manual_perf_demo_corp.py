"""Time remote recommendation fetch for LYQD Demo Corp.

Run:
  bench --site mytra.demo execute lyqd.tests.manual_perf_demo_corp.run
"""

from __future__ import annotations

import time

import frappe


def run():
	from lyqd.recommendations.core import get_liability_recommendations
	from lyqd.recommendations import remote as remote_mod
	from lyqd.api.spa import list_upcoming_payments, get_morning_mis

	company = "LYQD Demo Corp"
	out = {}

	cfg = frappe.get_all(
		"LYQD Recommendation Account",
		filters={"parent": company},
		fields=["account", "show_references"],
	)
	out["configured_accounts"] = len(cfg)
	out["refs_off_accounts"] = sum(1 for r in cfg if not int(r.show_references or 0))
	out["refs_on_accounts"] = sum(1 for r in cfg if int(r.show_references or 0))

	# Count remote get_list round-trips during recommendations
	calls = {"get_list": 0, "gl_entry_pages": 0}
	orig = remote_mod.FrappeClient.get_list if hasattr(remote_mod, "FrappeClient") else None
	from frappe.frappeclient import FrappeClient

	_orig_get_list = FrappeClient.get_list

	def _counting_get_list(self, doctype, *args, **kwargs):
		calls["get_list"] += 1
		if doctype == "GL Entry":
			calls["gl_entry_pages"] += 1
		return _orig_get_list(self, doctype, *args, **kwargs)

	FrappeClient.get_list = _counting_get_list
	try:
		t0 = time.perf_counter()
		try:
			recs = get_liability_recommendations(company)
			out["recommendations_ok"] = True
			out["recommendations_count"] = len(recs.get("items") or [])
			out["recommendations_message"] = (recs.get("message") or "")[:160]
			out["source"] = recs.get("source")
			out["books_company"] = recs.get("books_company")
		except Exception as e:
			out["recommendations_ok"] = False
			out["recommendations_error"] = str(e)[:300]
		out["recommendations_s"] = round(time.perf_counter() - t0, 2)
		out["remote_get_list_calls"] = calls["get_list"]
		out["remote_gl_entry_pages"] = calls["gl_entry_pages"]
	finally:
		FrappeClient.get_list = _orig_get_list

	t0 = time.perf_counter()
	plan = list_upcoming_payments(company)
	out["list_upcoming_s"] = round(time.perf_counter() - t0, 2)
	out["plan_count"] = len(plan or [])

	t0 = time.perf_counter()
	mis = get_morning_mis(company, horizon_days=7)
	out["morning_mis_s"] = round(time.perf_counter() - t0, 2)
	out["mis_upcoming"] = len(mis.get("upcoming") or [])

	# Estimate: each refs-off account = ≥1 GL get_list (more if GL history is large)
	out["note"] = (
		"refs-off accounts each call remote GL Entry get_list (paginated). "
		"Big ERPNext sites multiply pages per account."
	)

	print(frappe.as_json(out, indent=2))
	return out
