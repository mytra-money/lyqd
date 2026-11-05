"""Create a multi-due Purchase Invoice on pwctech and accept installments onto the plan.

Run:
  bench --site mytra.demo execute lyqd.tests.manual_pwctech_pi_schedule.run
"""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe.utils import add_days, flt, getdate, today

from lyqd.recommendations.core import (
	accept_recommendation,
	expand_payment_schedule_item,
	get_liability_recommendations,
)
from lyqd.tests.manual_pwctech_e2e import BOOKS, LYQD, _ensure_fiscal_year, _log, _ok, _fail, setup_local_books_and_accounts


def _pick_expense() -> str:
	for name in (
		"Administrative Expenses - P",
		"Office Rent - P",
		"Indirect Expenses - P",
		"Cost of Goods Sold - P",
	):
		if frappe.db.exists("Account", name):
			acc = frappe.get_doc("Account", name)
			if not acc.is_group:
				return name
	rows = frappe.get_all(
		"Account",
		filters={"company": BOOKS, "root_type": "Expense", "is_group": 0},
		pluck="name",
		limit_page_length=1,
	)
	if not rows:
		frappe.throw("No expense account for pwctech")
	return rows[0]


def _patch_tax_withholding_import() -> None:
	"""bharat_compliance PI override imports TDS helpers removed from current ERPNext."""
	import erpnext.accounts.doctype.tax_withholding_category.tax_withholding_category as twc
	from erpnext.accounts.party import get_party_details as _gpd

	stubs = {
		"get_party_details": _gpd,
		"get_tax_withholding_details": lambda *a, **k: frappe._dict(),
		"get_cost_center": lambda *a, **k: None,
		"get_tax_row_for_tds": lambda *a, **k: None,
		"get_advance_vouchers": lambda *a, **k: [],
		"get_taxes_deducted_on_advances_allocated": lambda *a, **k: [],
		"get_deducted_tax": lambda *a, **k: 0,
		"get_lower_deduction_certificate": lambda *a, **k: None,
		"is_valid_certificate": lambda *a, **k: False,
		"get_lower_deduction_amount": lambda *a, **k: 0,
		"normal_round": lambda x, *a, **k: flt(x),
	}
	for name, fn in stubs.items():
		if not hasattr(twc, name):
			setattr(twc, name, fn)
	# Force re-import of bharat override after stubs exist
	import sys

	sys.modules.pop("bharat_compliance.overrides.purchase_invoice", None)
	frappe.clear_cache(doctype="Purchase Invoice")
	try:
		from frappe.model import document as doc_mod

		site = getattr(frappe.local, "site", None)
		controllers = getattr(doc_mod, "controllers", None)
		if isinstance(controllers, dict) and site in controllers:
			controllers[site].pop("Purchase Invoice", None)
	except Exception:
		pass


def create_multi_due_purchase_invoice() -> dict[str, Any]:
	"""Submit a PI with two Payment Schedule rows (40% / 60%)."""
	_ensure_fiscal_year()
	setup_local_books_and_accounts()
	_patch_tax_withholding_import()

	# Prefer a supplier without tax withholding (broken import on this bench)
	supplier = None
	for row in frappe.get_all(
		"Supplier",
		fields=["name", "tax_withholding_category"],
		limit_page_length=50,
	):
		if not row.tax_withholding_category:
			supplier = row.name
			break
	if not supplier:
		groups = frappe.get_all("Supplier Group", pluck="name", limit_page_length=1)
		supplier_doc = frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": "LYQD Schedule Test Supplier",
				"supplier_group": groups[0] if groups else "All Supplier Groups",
				"tax_withholding_category": "",
			}
		)
		supplier_doc.insert(ignore_permissions=True)
		supplier = supplier_doc.name
		frappe.db.commit()
	else:
		# Ensure TDS category cleared for this run
		frappe.db.set_value("Supplier", supplier, "tax_withholding_category", None)

	expense = _pick_expense()
	cc = (
		frappe.get_all(
			"Cost Center",
			filters={"company": BOOKS, "is_group": 0},
			pluck="name",
			limit_page_length=1,
		)
		or [None]
	)[0]
	creditors = "Creditors - P"
	if not frappe.db.exists("Account", creditors):
		frappe.throw(f"Missing {creditors}")

	posting = getdate(today())
	# Both within default recommendation horizon (max(policy, 30) days)
	due1 = add_days(posting, 7)
	due2 = add_days(posting, 21)
	grand = 10_000.0
	amt1 = 4_000.0
	amt2 = 6_000.0

	pi = frappe.get_doc(
		{
			"doctype": "Purchase Invoice",
			"company": BOOKS,
			"supplier": supplier,
			"posting_date": posting,
			"due_date": due2,
			"credit_to": creditors,
			"update_stock": 0,
			"apply_tds": 0,
			"tax_withholding_category": "",
			"items": [
				{
					"item_code": None,
					"item_name": "LYQD multi-due service",
					"description": "Payment schedule e2e",
					"qty": 1,
					"uom": "Nos",
					"rate": grand,
					"expense_account": expense,
					"cost_center": cc,
				}
			],
		}
	)
	# Avoid broken tax-withholding import path on this bench
	pi.flags.ignore_tax_withholding = True
	# Clear auto schedule then set two installments
	pi.set("payment_schedule", [])
	pi.append(
		"payment_schedule",
		{
			"due_date": due1,
			"invoice_portion": 40,
			"payment_amount": amt1,
			"outstanding": amt1,
			"base_payment_amount": amt1,
			"base_outstanding": amt1,
		},
	)
	pi.append(
		"payment_schedule",
		{
			"due_date": due2,
			"invoice_portion": 60,
			"payment_amount": amt2,
			"outstanding": amt2,
			"base_payment_amount": amt2,
			"base_outstanding": amt2,
		},
	)
	pi.insert(ignore_permissions=True)
	pi.submit()
	frappe.db.commit()
	pi.reload()

	sched = [
		{
			"name": r.name,
			"due_date": str(r.due_date),
			"payment_amount": flt(r.payment_amount),
			"outstanding": flt(r.outstanding),
		}
		for r in pi.payment_schedule
	]
	return {
		"pi": pi.name,
		"outstanding": flt(pi.outstanding_amount),
		"schedule": sched,
		"supplier": supplier,
	}


def run() -> dict[str, Any]:
	results: dict[str, Any] = {"cases": []}

	def case(name: str, fn):
		try:
			detail = fn()
			_ok(name, json.dumps(detail, default=str) if detail is not None else "")
			results["cases"].append({"name": name, "ok": True, "detail": detail})
		except Exception as e:
			frappe.log_error(title=f"LYQD PI schedule e2e · {name}")
			_fail(name, frappe.get_traceback())
			results["cases"].append({"name": name, "ok": False, "detail": str(e)})
			frappe.db.rollback()

	created: dict[str, Any] = {}

	def create_pi():
		nonlocal created
		created = create_multi_due_purchase_invoice()
		assert len(created["schedule"]) >= 2, created
		assert abs(created["outstanding"] - 10_000) < 0.05, created
		return created

	case("create_multi_due_pi", create_pi)

	def expand_unit():
		item = {
			"grain": "voucher",
			"source_doctype": "Purchase Invoice",
			"source_name": created["pi"],
			"title": f"Test · Purchase Invoice {created['pi']}",
			"amount": created["outstanding"],
			"due_date": created["schedule"][-1]["due_date"],
			"category": "Vendor",
			"cash_effect": "Outflow",
			"account": "Creditors - P",
		}
		parts = expand_payment_schedule_item(item, lyqd_company=LYQD)
		assert len(parts) == 2, parts
		assert all(p.get("source_row") for p in parts), parts
		dues = sorted(p["due_date"] for p in parts)
		assert dues == sorted(s["due_date"] for s in created["schedule"]), (dues, created["schedule"])
		total = sum(flt(p["amount"]) for p in parts)
		assert abs(total - 10_000) < 0.05, total
		return {"parts": len(parts), "amounts": [p["amount"] for p in parts], "dues": dues}

	case("expand_payment_schedule_item", expand_unit)

	def recommendations_show_installments():
		bundle = get_liability_recommendations(LYQD, horizon_days=60)
		rows = [
			i
			for i in bundle.get("items") or []
			if i.get("source_doctype") == "Purchase Invoice" and i.get("source_name") == created["pi"]
		]
		assert len(rows) >= 2, {"count": len(rows), "sample": rows[:3], "msg": bundle.get("message")}
		assert all(r.get("source_row") for r in rows), rows
		return {
			"count": len(rows),
			"rows": [
				{"due": r.get("due_date"), "amt": r.get("amount"), "row": r.get("source_row"), "title": r.get("title")}
				for r in rows
			],
		}

	case("recommendations_list_installments", recommendations_show_installments)

	accepted_names: list[str] = []

	def accept_both():
		bundle = get_liability_recommendations(LYQD, horizon_days=60)
		rows = [
			i
			for i in bundle.get("items") or []
			if i.get("source_doctype") == "Purchase Invoice" and i.get("source_name") == created["pi"]
		]
		assert len(rows) >= 2, rows
		for i in rows:
			doc = accept_recommendation(
				LYQD,
				i["source_doctype"],
				i["source_name"],
				amount=i.get("amount"),
				title=i.get("title"),
				category=i.get("category") or "Vendor",
				due_date=i.get("due_date"),
				account=i.get("account"),
				cash_effect=i.get("cash_effect") or "Outflow",
				source_row=i.get("source_row"),
			)
			accepted_names.append(doc["name"])
			assert doc.get("source_row") == i.get("source_row"), doc
		frappe.db.commit()
		# Should no longer appear in recommendations
		again = [
			i
			for i in get_liability_recommendations(LYQD).get("items") or []
			if i.get("source_name") == created["pi"]
		]
		assert not again, again
		planned = frappe.get_all(
			"LYQD Upcoming Payment",
			filters={"company": LYQD, "source_name": created["pi"], "status": "Planned"},
			fields=["name", "due_date", "amount", "source_row", "title"],
			order_by="due_date asc",
		)
		assert len(planned) >= 2, planned
		return {"accepted": accepted_names, "planned": planned}

	case("accept_installments_to_plan", accept_both)

	passed = sum(1 for c in results["cases"] if c["ok"])
	failed = sum(1 for c in results["cases"] if not c["ok"])
	results["passed"] = passed
	results["failed"] = failed
	results["pi"] = created.get("pi")
	_log(f"DONE  {passed} passed, {failed} failed · PI={created.get('pi')}")
	return results
