"""
Demo seed for LYQD Desk PoC.

Usage:
  bench --site <site> execute lyqd.setup.seed.seed_demo
"""

from __future__ import annotations

import calendar

import frappe
from frappe.utils import add_days, get_last_day, getdate, nowdate, today


DEMO_COMPANY = "LYQD Demo Corp"
DEMO_ABBR = "LDC"
DEMO_BANK = "LYQD Demo Bank"
DEMO_BANK_ACCOUNT_NAME = "LYQD Operating Account"
CASH_AMOUNT = 4_80_00_000  # ₹4.8 Cr
BUFFER = 50_00_000  # ₹50 L — makes explanation non-zero
RESTRICTED = 0


def seed_demo(force: bool = False) -> dict:
	"""Create company, bank cash, policy, and upcoming payments for the demo script."""
	frappe.flags.in_install = False
	company = ensure_company()
	bank_account = ensure_bank_account(company)
	ensure_cash(company, bank_account)
	policy = ensure_policy(company)
	payments = ensure_upcoming_payments(company, force=force)
	ensure_settings()

	from lyqd.cash.surplus import compute_surplus

	s7 = compute_surplus(company, horizon_days=7)
	s30 = compute_surplus(company, horizon_days=30)

	summary = {
		"company": company,
		"bank_account": bank_account,
		"policy": policy,
		"upcoming_payments": payments,
		"surplus_7d": s7.investable_surplus,
		"surplus_30d": s30.investable_surplus,
		"upcoming_7d": s7.upcoming_total,
		"upcoming_30d": s30.upcoming_total,
	}
	# bench execute does not auto-commit; persist demo seed after CLI exit
	frappe.db.commit()  # nosemgrep
	print(_format_summary(summary))
	return summary


def ensure_settings() -> None:
	settings = frappe.get_single("LYQD Settings")
	settings.tagline = "Make idle cash work smarter."
	settings.display_scheme_label = "ICICI Prudential Liquid Fund"
	settings.display_scheme_isin = "INF109K01VQ1"
	settings.default_forecast_horizon_days = 7
	settings.enable_draft_proposals = 1
	settings.flags.ignore_permissions = True
	settings.save()


def ensure_company() -> str:
	if frappe.db.exists("LYQD Company", DEMO_COMPANY):
		return DEMO_COMPANY

	doc = frappe.get_doc(
		{
			"doctype": "LYQD Company",
			"company_name": DEMO_COMPANY,
			"abbr": DEMO_ABBR,
			"default_currency": "INR",
			"is_active": 1,
			"books_source": "Manual",
			"books_company": DEMO_COMPANY,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def ensure_bank_account(company: str) -> str:
	from lyqd.cash.bank_cash import create_company_bank_account

	existing = frappe.db.get_value(
		"LYQD Bank Account",
		{"company": company, "account_name": DEMO_BANK_ACCOUNT_NAME},
	)
	if existing:
		return existing

	created = create_company_bank_account(
		company=company,
		account_name=DEMO_BANK_ACCOUNT_NAME,
		bank=DEMO_BANK,
		opening_balance=0,
		add_to_policy=True,
		is_default=True,
		allow_when_remote=True,
	)
	return created["bank_account"]


def ensure_cash(company: str, bank_account: str) -> str:
	"""Seed daily statement balance into LYQD Bank Balance."""
	from lyqd.cash.bank_cash import set_statement_balance

	as_on = today()
	set_statement_balance(bank_account, CASH_AMOUNT, as_on)
	return f"{bank_account}@{as_on}"


def ensure_policy(company: str) -> str:
	"""Set Policy tab fields on the LYQD Company (demo buffers / horizon)."""
	doc = frappe.get_doc("LYQD Company", company)
	doc.min_liquidity_buffer = BUFFER
	doc.restricted_cash = RESTRICTED
	doc.default_forecast_horizon_days = 7
	doc.notes = doc.notes or "Demo policy — 7d default horizon; dashboard also shows 30d"
	doc.flags.ignore_permissions = True
	doc.save()
	return doc.name


def _demo_due_dates():
	"""
	Dates that satisfy the demo script:
	- 7d horizon: GST in, salary + LC out
	- 30d horizon: all three in
	"""
	as_of = getdate(today())
	gst_due = add_days(as_of, 5)
	lc_due = add_days(as_of, 12)

	month_end = get_last_day(as_of)
	# If month-end falls inside 7d, push salary to next month-end so 7d demo stays clean.
	if month_end <= add_days(as_of, 7):
		year = as_of.year + (1 if as_of.month == 12 else 0)
		month = 1 if as_of.month == 12 else as_of.month + 1
		last_day = calendar.monthrange(year, month)[1]
		salary_due = getdate(f"{year}-{month:02d}-{last_day:02d}")
	else:
		salary_due = month_end

	# Keep salary inside 30d window
	if salary_due > add_days(as_of, 30):
		salary_due = add_days(as_of, 28)

	return {
		"gst": gst_due,
		"lc": lc_due,
		"salary": salary_due,
	}


def ensure_upcoming_payments(company: str, force: bool = False) -> list[str]:
	dates = _demo_due_dates()
	specs = [
		{
			"title": "Monthly Salary",
			"category": "Salary",
			"amount": 1_20_00_000,
			"due_date": dates["salary"],
			"notes": "Demo — month-end payroll (outside 7d when near month-end)",
		},
		{
			"title": "Import LC Margin",
			"category": "Import-LC",
			"amount": 80_00_000,
			"due_date": dates["lc"],
			"notes": "Demo — LC due in ~12 days",
		},
		{
			"title": "GST Payment",
			"category": "Tax",
			"amount": 15_00_000,
			"due_date": dates["gst"],
			"notes": "Demo — GST due in ~5 days",
		},
	]

	# Clear prior demo Planned rows for this company when force-reseeding
	if force:
		for name in frappe.get_all(
			"LYQD Upcoming Payment",
			filters={"company": company, "notes": ("like", "Demo —%")},
			pluck="name",
		):
			frappe.delete_doc("LYQD Upcoming Payment", name, force=True, ignore_permissions=True)

	created: list[str] = []
	for spec in specs:
		existing = frappe.db.get_value(
			"LYQD Upcoming Payment",
			{
				"company": company,
				"title": spec["title"],
				"status": "Planned",
			},
		)
		if existing and not force:
			doc = frappe.get_doc("LYQD Upcoming Payment", existing)
			doc.amount = spec["amount"]
			doc.due_date = spec["due_date"]
			doc.category = spec["category"]
			doc.notes = spec["notes"]
			doc.flags.ignore_permissions = True
			doc.save()
			created.append(doc.name)
			continue

		doc = frappe.get_doc(
			{
				"doctype": "LYQD Upcoming Payment",
				"company": company,
				"status": "Planned",
				**spec,
			}
		)
		doc.insert(ignore_permissions=True)
		created.append(doc.name)
	return created


def _format_summary(summary: dict) -> str:
	return (
		f"\nLYQD demo seed ready for company={summary['company']}\n"
		f"  Bank cash ≈ ₹{CASH_AMOUNT/1e7:.2f} Cr\n"
		f"  Upcoming 7d reserved  = {summary['upcoming_7d']}\n"
		f"  Upcoming 30d reserved = {summary['upcoming_30d']}\n"
		f"  Investable 7d         = {summary['surplus_7d']}\n"
		f"  Investable 30d        = {summary['surplus_30d']}\n"
		f"Open Desk → LYQD workspace to demo.\n"
	)
