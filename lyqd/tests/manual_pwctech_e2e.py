"""E2E battery for LYQD company ``pwctech`` against **local** ERPNext (company ``pwctech``).

Run:
  bench --site mytra.demo execute lyqd.tests.manual_pwctech_e2e.run
"""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe.utils import add_days, flt, getdate, today

LYQD = "pwctech"
BOOKS = "pwctech"  # local ERPNext Company name (== LYQD Company)


def _log(msg: str, **extra: Any) -> None:
	line = msg
	if extra:
		line += " | " + json.dumps(extra, default=str)
	print(line)


def _ok(name: str, detail: str = "") -> None:
	_log(f"PASS  {name}" + (f" — {detail}" if detail else ""))


def _fail(name: str, detail: str) -> None:
	_log(f"FAIL  {name} — {detail}")


def clear_lyqd_plans(company: str = LYQD) -> dict[str, int]:
	counts: dict[str, int] = {}
	frappe.db.sql(
		"update `tabLYQD Upcoming Payment` set parent_payment=null where company=%s",
		company,
	)
	for status in ("Planned", "Paid", "Cancelled"):
		names = frappe.get_all(
			"LYQD Upcoming Payment",
			filters={"company": company, "status": status},
			pluck="name",
		)
		for name in names:
			frappe.delete_doc("LYQD Upcoming Payment", name, force=True, ignore_permissions=True)
		counts[f"upcoming_{status}"] = len(names)

	if frappe.db.exists("DocType", "LYQD Draft Proposal"):
		props = frappe.get_all("LYQD Draft Proposal", filters={"company": company}, pluck="name")
		for name in props:
			frappe.delete_doc("LYQD Draft Proposal", name, force=True, ignore_permissions=True)
		counts["draft_proposals"] = len(props)

	frappe.db.commit()
	return counts


def setup_local_books_and_accounts() -> dict[str, Any]:
	"""Point LYQD at local ERPNext company and rebuild recommendation accounts (- P)."""
	doc = frappe.get_doc("LYQD Company", LYQD)
	doc.erpnext_enabled = 1
	doc.is_erpnext_in_the_current_site = 1
	doc.books_source = "This Site"
	doc.books_company = BOOKS
	doc.enable_purchase_invoice_recommendations = 1

	parent = "Output Tax IGST - P"
	# account, show_references, parent_account
	wanted = [
		(parent, 0, None),
		("Output Tax CGST - P", 0, parent),
		("Output Tax SGST - P", 0, parent),
		("Input Tax IGST - P", 0, parent),
		("Input Tax CGST - P", 0, parent),
		("Input Tax SGST - P", 0, parent),
		("Creditors - P", 1, None),
		("TDS Payable - P", 0, None),
		("Customs Duty Payable - P", 0, None),
		("Payroll Payable - P", 0, None),
	]

	doc.set("recommendation_accounts", [])
	missing = []
	for account, refs, parent_acc in wanted:
		if not frappe.db.exists("Account", account):
			missing.append(account)
			continue
		doc.append(
			"recommendation_accounts",
			{
				"account": account,
				"account_name": frappe.db.get_value("Account", account, "account_name") or account,
				"show_references": refs,
				"parent_account": parent_acc or "",
			},
		)
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {
		"books_company": doc.books_company,
		"rows": len(doc.recommendation_accounts),
		"missing": missing,
	}


def _pick_expense() -> str | None:
	for name in (
		"Administrative Expenses - P",
		"Office Rent - P",
		"Indirect Expenses - P",
		"GST Expense - P",
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
	return rows[0] if rows else None


def _pick_bank() -> str | None:
	rows = frappe.get_all(
		"Account",
		filters={"company": BOOKS, "account_type": "Bank", "is_group": 0},
		pluck="name",
		limit_page_length=1,
	)
	return rows[0] if rows else None


def _ensure_fiscal_year() -> str:
	"""Ensure an open Fiscal Year covering today (create 2026-2027 if needed)."""
	as_of = getdate(today())
	existing = frappe.db.sql(
		"""
		select name from `tabFiscal Year`
		where disabled=0 and year_start_date<=%s and year_end_date>=%s
		limit 1
		""",
		(as_of, as_of),
	)
	if existing:
		return existing[0][0]
	# India FY for calendar year 2026 falls in Apr 2026 – Mar 2027
	name = "2026-2027"
	if frappe.db.exists("Fiscal Year", name):
		doc = frappe.get_doc("Fiscal Year", name)
		doc.disabled = 0
		doc.save(ignore_permissions=True)
		frappe.db.commit()
		return name
	doc = frappe.get_doc(
		{
			"doctype": "Fiscal Year",
			"year": name,
			"year_start_date": "2026-04-01",
			"year_end_date": "2027-03-31",
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return name


def seed_local_transactions() -> dict[str, Any]:
	"""Post Journal Entries so recommendations have balances to surface."""
	fy = _ensure_fiscal_year()
	created: list[str] = []
	errors: list[str] = []
	expense = _pick_expense()
	bank = _pick_bank()
	creditors = "Creditors - P"
	supplier = (frappe.get_all("Supplier", pluck="name", limit_page_length=1) or [None])[0]
	posting = today()

	def _je(remark: str, accounts: list[dict]) -> str | None:
		je = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"company": BOOKS,
				"posting_date": posting,
				"voucher_type": "Journal Entry",
				"user_remark": remark,
				"accounts": accounts,
			}
		)
		try:
			je.insert(ignore_permissions=True)
			je.submit()
			frappe.db.commit()
			created.append(je.name)
			return je.name
		except Exception as e:
			frappe.db.rollback()
			errors.append(f"{remark}: {e}")
			return None

	# 1) Vendor payable
	if expense and frappe.db.exists("Account", creditors):
		row_cred = {
			"account": creditors,
			"credit_in_account_currency": 25000,
			"debit_in_account_currency": 0,
		}
		if supplier:
			row_cred["party_type"] = "Supplier"
			row_cred["party"] = supplier
		_je(
			"LYQD e2e — creditors payable",
			[
				{"account": expense, "debit_in_account_currency": 25000, "credit_in_account_currency": 0},
				row_cred,
			],
		)

	# 2) Output IGST liability
	if bank and frappe.db.exists("Account", "Output Tax IGST - P"):
		_je(
			"LYQD e2e — output IGST",
			[
				{"account": bank, "debit_in_account_currency": 18000, "credit_in_account_currency": 0},
				{
					"account": "Output Tax IGST - P",
					"credit_in_account_currency": 18000,
					"debit_in_account_currency": 0,
				},
			],
		)

	# 3) Output CGST / SGST
	if bank and frappe.db.exists("Account", "Output Tax CGST - P"):
		_je(
			"LYQD e2e — output CGST",
			[
				{"account": bank, "debit_in_account_currency": 4500, "credit_in_account_currency": 0},
				{
					"account": "Output Tax CGST - P",
					"credit_in_account_currency": 4500,
					"debit_in_account_currency": 0,
				},
			],
		)
	if bank and frappe.db.exists("Account", "Output Tax SGST - P"):
		_je(
			"LYQD e2e — output SGST",
			[
				{"account": bank, "debit_in_account_currency": 4500, "credit_in_account_currency": 0},
				{
					"account": "Output Tax SGST - P",
					"credit_in_account_currency": 4500,
					"debit_in_account_currency": 0,
				},
			],
		)

	# 4) Input IGST setoff (asset debit)
	if bank and frappe.db.exists("Account", "Input Tax IGST - P"):
		_je(
			"LYQD e2e — input IGST setoff",
			[
				{
					"account": "Input Tax IGST - P",
					"debit_in_account_currency": 5000,
					"credit_in_account_currency": 0,
				},
				{"account": bank, "credit_in_account_currency": 5000, "debit_in_account_currency": 0},
			],
		)

	# 5) Input CGST credit balance (asset credit → Outflow)
	if bank and frappe.db.exists("Account", "Input Tax CGST - P"):
		_je(
			"LYQD e2e — input CGST credit balance",
			[
				{"account": bank, "debit_in_account_currency": 1200, "credit_in_account_currency": 0},
				{
					"account": "Input Tax CGST - P",
					"credit_in_account_currency": 1200,
					"debit_in_account_currency": 0,
				},
			],
		)

	# 6) TDS payable
	if expense and frappe.db.exists("Account", "TDS Payable - P"):
		_je(
			"LYQD e2e — TDS payable",
			[
				{"account": expense, "debit_in_account_currency": 3000, "credit_in_account_currency": 0},
				{
					"account": "TDS Payable - P",
					"credit_in_account_currency": 3000,
					"debit_in_account_currency": 0,
				},
			],
		)

	# Optional: open Purchase Invoice for voucher-grain Creditors
	pi_name = None
	if supplier and expense and frappe.db.exists("Account", creditors):
		try:
			# Prefer simple PI if Item exists; else skip
			item = (frappe.get_all("Item", filters={"is_purchase_item": 1}, pluck="name", limit_page_length=1) or [None])[0]
			if item:
				pi = frappe.get_doc(
					{
						"doctype": "Purchase Invoice",
						"company": BOOKS,
						"supplier": supplier,
						"posting_date": today(),
						"due_date": add_days(today(), 15),
						"credit_to": creditors,
						"items": [
							{
								"item_code": item,
								"qty": 1,
								"rate": 8000,
								"expense_account": expense,
							}
						],
					}
				)
				pi.insert(ignore_permissions=True)
				pi.submit()
				frappe.db.commit()
				pi_name = pi.name
				created.append(pi.name)
		except Exception as e:
			frappe.db.rollback()
			errors.append(f"PI: {e}")

	return {
		"fiscal_year": fy,
		"created": created,
		"errors": errors,
		"pi": pi_name,
		"expense": expense,
		"bank": bank,
	}


def run() -> dict[str, Any]:
	frappe.set_user("Administrator")
	results: dict[str, Any] = {"company": LYQD, "cases": []}

	def case(name: str, fn):
		try:
			detail = fn()
			_ok(name, detail if isinstance(detail, str) else json.dumps(detail, default=str)[:280])
			results["cases"].append({"name": name, "ok": True, "detail": detail})
		except Exception as e:
			frappe.log_error(title=f"LYQD e2e {name}")
			_fail(name, str(e))
			results["cases"].append({"name": name, "ok": False, "detail": str(e)})

	from lyqd.recommendations.core import (
		accept_recommendation,
		get_liability_recommendations,
		interpret_account_gl_balance,
		relink_plan_parents,
		set_upcoming_balance_as_of,
		sync_nested_account_plans,
		sync_planned_from_books,
		sync_upcoming_payment_from_books,
		_find_account_grain_plan,
		_parent_account_map,
		_net_asset_gl,
	)
	from lyqd.recommendations.settings import is_erpnext_integration_enabled, is_remote_source

	parent_plan = None
	bundle: dict[str, Any] = {"items": []}

	def preconditions():
		assert frappe.db.exists("LYQD Company", LYQD)
		assert frappe.db.exists("Company", BOOKS)
		setup = setup_local_books_and_accounts()
		assert is_erpnext_integration_enabled(LYQD)
		assert not is_remote_source(LYQD)
		assert setup["rows"] >= 5, setup
		return setup

	case("setup_local_erpnext_and_accounts", preconditions)
	case("clear_plans", lambda: clear_lyqd_plans(LYQD))
	case("seed_local_transactions", seed_local_transactions)

	def recommendations():
		nonlocal bundle
		bundle = get_liability_recommendations(LYQD)
		items = bundle.get("items") or []
		assert bundle.get("enabled"), bundle.get("message")
		assert items, f"no items: {bundle.get('message')}"
		grains: dict[str, int] = {}
		effects: dict[str, int] = {}
		for i in items:
			grains[i.get("grain") or "?"] = grains.get(i.get("grain") or "?", 0) + 1
			effects[i.get("cash_effect") or "?"] = effects.get(i.get("cash_effect") or "?", 0) + 1
		# Expect Output IGST and Input IGST setoff among account grains
		sources = {i.get("source_name") for i in items}
		return {
			"count": len(items),
			"grains": grains,
			"cash_effects": effects,
			"has_output_igst": "Output Tax IGST - P" in sources,
			"has_input_igst": "Input Tax IGST - P" in sources,
			"has_input_cgst_credit": any(
				i.get("source_name") == "Input Tax CGST - P" and i.get("cash_effect") == "Outflow"
				for i in items
			),
		}

	case("get_recommendations", recommendations)

	def nesting_map():
		pm = _parent_account_map(LYQD)
		assert pm, "parent map empty"
		assert all(v == "Output Tax IGST - P" for v in pm.values()), pm
		return {"size": len(pm), "children": list(pm.keys())}

	case("parent_account_map", nesting_map)

	def accept_parent():
		nonlocal parent_plan
		items = bundle.get("items") or []
		parent_item = next(
			(
				i
				for i in items
				if i.get("source_doctype") == "Account" and i.get("source_name") == "Output Tax IGST - P"
			),
			None,
		)
		assert parent_item, "Output Tax IGST - P not in recommendations"
		row = accept_recommendation(
			LYQD,
			"Account",
			"Output Tax IGST - P",
			amount=parent_item.get("amount"),
			title=parent_item.get("title"),
			category=parent_item.get("category") or "Tax",
			due_date=add_days(today(), 20),
			account="Output Tax IGST - P",
			cash_effect=parent_item.get("cash_effect") or "Outflow",
		)
		parent_plan = row["name"]
		frappe.db.commit()
		return {"plan": parent_plan, "amount": row.get("amount")}

	case("accept_parent_output_igst", accept_parent)

	def accept_voucher():
		items = bundle.get("items") or []
		v = next((i for i in items if i.get("grain") == "voucher"), None)
		if not v:
			return {"skipped": True}
		row = accept_recommendation(
			LYQD,
			v["source_doctype"],
			v["source_name"],
			amount=v.get("amount"),
			title=v.get("title"),
			category=v.get("category"),
			due_date=v.get("due_date") or add_days(today(), 10),
			account=v.get("account"),
			cash_effect=v.get("cash_effect"),
		)
		frappe.db.commit()
		return {"plan": row["name"], "source": f"{v['source_doctype']} {v['source_name']}", "amount": row.get("amount")}

	case("accept_voucher_if_any", accept_voucher)

	def sync_children():
		out = sync_nested_account_plans(LYQD)
		frappe.db.commit()
		assert parent_plan
		kids = frappe.get_all(
			"LYQD Upcoming Payment",
			filters={"parent_payment": parent_plan, "status": "Planned"},
			fields=["name", "source_name", "amount", "cash_effect"],
		)
		assert kids, f"no children created: {out}"
		by_acc = {k.source_name: k for k in kids}
		# Assets: debit → Setoff, credit → Outflow (after seed)
		if "Input Tax IGST - P" in by_acc:
			assert by_acc["Input Tax IGST - P"].cash_effect == "Setoff", by_acc["Input Tax IGST - P"]
		if "Input Tax CGST - P" in by_acc and flt(by_acc["Input Tax CGST - P"].amount) > 0:
			# After credit-balance seed this must be Outflow; debit seed → Setoff
			signed = _net_asset_gl(BOOKS, "Input Tax CGST - P", today())
			want = "Outflow" if signed < -0.01 else "Setoff"
			assert by_acc["Input Tax CGST - P"].cash_effect == want, {
				"row": by_acc["Input Tax CGST - P"],
				"signed": signed,
				"want": want,
			}
		return {
			"created": out.get("created_count"),
			"children": len(kids),
			"rows": [
				{"acc": k.source_name, "amt": k.amount, "ce": k.cash_effect} for k in kids
			],
		}

	case("sync_nested_children", sync_children)

	def asset_credit():
		acc = "Input Tax CGST - P"
		# Force a net credit on the asset (extra credit JE if still debit)
		signed = _net_asset_gl(BOOKS, acc, today())
		bank = _pick_bank()
		if signed >= -0.01 and bank:
			# Credit enough to flip into credit balance (+ 2000 buffer)
			credit_amt = flt(signed) + 2000
			je = frappe.get_doc(
				{
					"doctype": "Journal Entry",
					"company": BOOKS,
					"posting_date": today(),
					"voucher_type": "Journal Entry",
					"user_remark": "LYQD e2e — flip Input CGST to credit",
					"accounts": [
						{
							"account": bank,
							"debit_in_account_currency": credit_amt,
							"credit_in_account_currency": 0,
						},
						{
							"account": acc,
							"credit_in_account_currency": credit_amt,
							"debit_in_account_currency": 0,
						},
					],
				}
			)
			je.insert(ignore_permissions=True)
			je.submit()
			frappe.db.commit()
			signed = _net_asset_gl(BOOKS, acc, today())
		interp = interpret_account_gl_balance("Asset", signed, acc)
		assert signed < -0.01, f"expected credit balance, got {signed}"
		assert interp["cash_effect"] == "Outflow", interp
		plan = _find_account_grain_plan(LYQD, acc)
		assert plan, "missing child plan for Input Tax CGST"
		sync_upcoming_payment_from_books(plan)
		frappe.db.commit()
		ce = frappe.db.get_value("LYQD Upcoming Payment", plan, ["cash_effect", "amount"], as_dict=True)
		assert ce.cash_effect == "Outflow", ce
		assert abs(flt(ce.amount) - flt(interp["amount"])) < 0.02
		return {"signed": signed, "amount": ce.amount, "cash_effect": ce.cash_effect}

	case("asset_credit_balance_outflow", asset_credit)

	as_of = str(getdate(add_days(today(), -1)))

	def freeze():
		assert parent_plan
		out = set_upcoming_balance_as_of(parent_plan, as_of, cascade_children=True, sync=True)
		frappe.db.commit()
		assert str(frappe.db.get_value("LYQD Upcoming Payment", parent_plan, "balance_as_of")) == as_of
		kids = frappe.get_all(
			"LYQD Upcoming Payment",
			filters={"parent_payment": parent_plan},
			fields=["name", "balance_as_of"],
		)
		assert all(str(k.balance_as_of or "") == as_of for k in kids), kids
		return {"as_of": as_of, "n": len(out.get("updated") or [])}

	case("freeze_cascades", freeze)

	def unfreeze():
		assert parent_plan
		out = set_upcoming_balance_as_of(parent_plan, None, cascade_children=True, sync=True)
		frappe.db.commit()
		assert not frappe.db.get_value("LYQD Upcoming Payment", parent_plan, "balance_as_of")
		kids = frappe.get_all(
			"LYQD Upcoming Payment",
			filters={"parent_payment": parent_plan},
			pluck="balance_as_of",
		)
		assert all(not k for k in kids)
		return {"cleared": len(out.get("updated") or [])}

	case("unfreeze_cascades", unfreeze)

	def unlink():
		child_acc = "Output Tax CGST - P"
		child_plan = _find_account_grain_plan(LYQD, child_acc)
		assert child_plan
		assert frappe.db.get_value("LYQD Upcoming Payment", child_plan, "parent_payment") == parent_plan
		doc = frappe.get_doc("LYQD Company", LYQD)
		for r in doc.recommendation_accounts:
			if r.account == child_acc:
				r.parent_account = ""
		doc.save(ignore_permissions=True)
		rel = relink_plan_parents(LYQD)
		frappe.db.commit()
		assert not frappe.db.get_value("LYQD Upcoming Payment", child_plan, "parent_payment")
		# restore
		doc = frappe.get_doc("LYQD Company", LYQD)
		for r in doc.recommendation_accounts:
			if r.account == child_acc:
				r.parent_account = "Output Tax IGST - P"
				r.show_references = 0
		doc.save(ignore_permissions=True)
		sync_nested_account_plans(LYQD)
		frappe.db.commit()
		assert (
			frappe.db.get_value("LYQD Upcoming Payment", child_plan, "parent_payment") == parent_plan
		)
		return {"unlinked_then_restored": child_acc, "relink": rel}

	case("unlink_and_relink_child", unlink)

	def accept_more():
		accepted = []
		for i in get_liability_recommendations(LYQD).get("items") or []:
			if i.get("source_doctype") != "Account":
				continue
			if _find_account_grain_plan(LYQD, i["source_name"]):
				continue
			row = accept_recommendation(
				LYQD,
				"Account",
				i["source_name"],
				amount=i.get("amount"),
				title=i.get("title"),
				category=i.get("category"),
				due_date=add_days(today(), 15),
				account=i.get("account"),
				cash_effect=i.get("cash_effect"),
			)
			accepted.append({"name": row["name"], "acc": i["source_name"], "ce": row.get("cash_effect")})
		sync_nested_account_plans(LYQD)
		frappe.db.commit()
		planned = frappe.get_all(
			"LYQD Upcoming Payment",
			filters={"company": LYQD, "status": "Planned"},
			fields=["name", "source_name", "parent_payment", "amount", "cash_effect"],
		)
		nested = sum(1 for p in planned if p.parent_payment)
		return {"accepted": accepted, "planned": len(planned), "nested": nested}

	case("accept_remaining_accounts", accept_more)

	def sync_all():
		out = sync_planned_from_books(LYQD)
		frappe.db.commit()
		return out.get("summary") or out

	case("sync_planned_from_books", sync_all)

	def group_net_sanity():
		"""Parent+children signed net should match sum of signed amounts."""
		assert parent_plan
		rows = frappe.get_all(
			"LYQD Upcoming Payment",
			filters={"company": LYQD, "status": "Planned"},
			fields=["name", "amount", "cash_effect", "parent_payment", "source_name"],
		)
		parent = next(r for r in rows if r.name == parent_plan)
		kids = [r for r in rows if r.parent_payment == parent_plan]

		def signed(r):
			amt = flt(r.amount)
			return -amt if r.cash_effect == "Setoff" else amt

		net = signed(parent) + sum(signed(k) for k in kids)
		return {
			"parent": parent.source_name,
			"parent_amt": parent.amount,
			"children": len(kids),
			"group_net": net,
		}

	case("group_net_sanity", group_net_sanity)

	passed = sum(1 for c in results["cases"] if c["ok"])
	failed = sum(1 for c in results["cases"] if not c["ok"])
	results["passed"] = passed
	results["failed"] = failed
	_log(f"DONE  {passed} passed, {failed} failed")
	return results
