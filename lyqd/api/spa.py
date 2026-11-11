"""Whitelisted APIs for the LYQD Vue SPA at /lyqd."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from lyqd.api.dashboard import (
	_default_company,
	create_surplus_run_doc,
	get_dashboard_metrics,
	get_surplus_explanation,
)
from lyqd.cash.bank_cash import get_eligible_bank_cash
from lyqd.cash.surplus import compute_surplus, get_policy, parse_horizon_days
from lyqd.setup.permissions import get_user_companies


@frappe.whitelist()
def get_boot_data() -> dict:
	from lyqd.recommendations.settings import settings_for_api

	companies = get_user_companies()
	default_company = frappe.defaults.get_user_default("LYQD Company")
	if default_company and default_company not in (companies or []):
		default_company = None
	default_company = default_company or (companies[0] if companies else None)
	settings = {}
	if frappe.db.exists("DocType", "LYQD Settings"):
		s = frappe.get_single("LYQD Settings")
		settings = {
			"default_forecast_horizon_days": s.default_forecast_horizon_days,
			"in_beta": int(getattr(s, "in_beta", 1) or 0),
			"tagline": s.tagline,
			"display_scheme_label": s.display_scheme_label,
			"display_scheme_isin": s.display_scheme_isin,
			"illustrative_idle_yield_pct": float(
				getattr(s, "illustrative_idle_yield_pct", 0) or 0
			),
			"illustrative_fd_yield_pct": float(
				getattr(s, "illustrative_fd_yield_pct", 3) or 3
			),
			"illustrative_liquid_yield_pct": float(
				getattr(s, "illustrative_liquid_yield_pct", 5.5) or 5.5
			),
		}
	# Per-company books + investment overlay for the active company
	company_settings = settings_for_api(default_company) if default_company else {}
	if company_settings:
		settings.update(
			{
				"investment_account_activated": company_settings.get(
					"investment_account_activated", 0
				),
				"investment_account_requested_on": company_settings.get(
					"investment_account_requested_on"
				),
			}
		)
	user_image = None
	if frappe.session.user and frappe.session.user != "Guest":
		user_image = frappe.db.get_value("User", frappe.session.user, "user_image")
	return {
		"user": frappe.session.user,
		"user_fullname": frappe.utils.get_fullname(frappe.session.user),
		"user_image": user_image,
		"companies": companies,
		"default_company": default_company,
		"roles": frappe.get_roles(),
		"settings": settings,
		"tagline": settings.get("tagline") or "Make idle cash work smarter.",
		"erpnext_integration_enabled": bool(company_settings.get("enabled")),
		"erpnext_installed": "erpnext" in frappe.get_installed_apps(),
		"company_settings": company_settings,
	}


@frappe.whitelist()
def list_local_erpnext_companies() -> dict:
	"""ERPNext Company names on this site (for This Site books binding)."""
	frappe.only_for(("System Manager", "LYQD Manager", "LYQD User"))
	if "erpnext" not in frappe.get_installed_apps():
		return {"companies": [], "erpnext_installed": False}
	if not frappe.db.exists("DocType", "Company"):
		return {"companies": [], "erpnext_installed": False}
	companies = frappe.get_all("Company", pluck="name", order_by="name asc")
	return {"companies": companies, "erpnext_installed": True}


@frappe.whitelist()
def set_current_company(company: str | None = None) -> dict:
	"""Remember the active LYQD Company for this user (survives refresh)."""
	company = (company or "").strip()
	if not company:
		frappe.throw(_("Company is required"))
	allowed = get_user_companies()
	if company not in allowed and "System Manager" not in frappe.get_roles():
		if frappe.session.user != "Administrator":
			frappe.throw(_("You do not have access to {0}").format(company))
	if not frappe.db.exists("LYQD Company", company):
		frappe.throw(_("LYQD Company {0} not found").format(company))
	frappe.defaults.set_user_default("LYQD Company", company)
	return {"company": company, "companies": allowed or get_user_companies()}



@frappe.whitelist()
def create_lyqd_company(
	company_name: str,
	abbr: str | None = None,
	books_source: str | None = None,
	books_company: str | None = None,
	remote_site_url: str | None = None,
	remote_api_key: str | None = None,
	remote_api_secret: str | None = None,
	mirror_banks: int | bool = 1,
) -> dict:
	"""
	Create a LYQD Company (Details + Books).

	Non–System Managers also get a User Permission on this company so it appears
	in their nav. Optional Other Site credentials are validated on save.
	"""
	from lyqd.setup.permissions import ensure_lyqd_company_user_permission

	frappe.only_for(("System Manager", "LYQD Manager", "LYQD User"))
	company_name = (company_name or "").strip()
	if not company_name:
		frappe.throw(_("Company name is required"))

	books_source = books_source or "Manual"
	if books_source not in ("Manual", "This Site", "Other Site"):
		books_source = "Manual"

	books_company = (books_company or "").strip()
	if books_source in ("This Site", "Other Site") and not books_company:
		frappe.throw(
			_(
				"Books company is required when ERPNext is enabled. "
				"Select the ERPNext Company this LYQD Company should use."
			)
		)
	if books_source == "This Site" and not frappe.db.exists("Company", books_company):
		frappe.throw(_("Company {0} was not found on this site.").format(books_company))

	created = False
	if frappe.db.exists("LYQD Company", company_name):
		# Existing name: only System Managers may "claim" it; others need a fresh name
		if "System Manager" not in frappe.get_roles() and frappe.session.user != "Administrator":
			frappe.throw(
				_("Company {0} already exists. Choose a different name.").format(company_name)
			)
		doc = frappe.get_doc("LYQD Company", company_name)
	else:
		doc = frappe.new_doc("LYQD Company")
		doc.company_name = company_name
		doc.abbr = abbr
		doc.is_active = 1
		doc.books_company = books_company
		doc.apply_books_source(books_source)
		doc.remote_site_url = (remote_site_url or "").strip() or None
		doc.remote_api_key = (remote_api_key or "").strip() or None
		if remote_api_secret:
			doc.remote_api_secret = remote_api_secret
		# only_for() already gates roles; ignore DocType/controller create chicken-and-egg
		# (User Permission is granted immediately after insert).
		doc.insert(ignore_permissions=True)
		created = True

	# Grant access for non–System Managers (onboarding / add from nav)
	perm_created = ensure_lyqd_company_user_permission(doc.name)
	frappe.defaults.set_user_default("LYQD Company", doc.name)

	payload = doc.as_dict()
	payload["created"] = created
	payload["user_permission_created"] = bool(perm_created)
	payload["companies"] = get_user_companies()

	if books_source == "Other Site" and int(mirror_banks or 0):
		try:
			from lyqd.cash.mirror_banks import mirror_remote_bank_accounts

			payload["bank_mirror"] = mirror_remote_bank_accounts(doc.name)
		except Exception as e:
			frappe.log_error(title="LYQD bank mirror on create company")
			payload["bank_mirror_error"] = str(e)

	return payload


@frappe.whitelist()
def get_cash_detail(company: str | None = None) -> dict:
	company = company or _default_company()
	return get_eligible_bank_cash(company)


@frappe.whitelist()
def set_daily_bank_balance(
	bank_account: str,
	balance: float | str,
	as_of: str | None = None,
) -> dict:
	"""Write today's (or as_of) statement closing on LYQD Bank Balance."""
	from lyqd.cash.bank_cash import set_statement_balance

	if not frappe.has_permission("LYQD Bank Account", "write", doc=bank_account):
		frappe.only_for(("System Manager", "LYQD Manager", "LYQD User"))
	return set_statement_balance(bank_account, flt(balance), as_of)


@frappe.whitelist()
def suggest_remote_bank_balance(
	bank_account: str,
	as_of: str | None = None,
) -> dict:
	"""Read-only remote Bank Account Balance suggestion for the Cash update dialog."""
	from lyqd.cash.bank_cash import suggest_remote_bank_balance as _suggest

	frappe.only_for(("System Manager", "LYQD Manager", "LYQD User"))
	return _suggest(bank_account, as_of)


@frappe.whitelist()
def get_morning_mis(company: str | None = None, horizon_days: int | str = 7) -> dict:
	"""Morning MIS: bank balances (BAB), liquid holdings, upcoming, redemption need."""
	from frappe.utils import today

	from lyqd.cash.bank_cash import default_bank_statement_as_of, get_eligible_bank_cash
	from lyqd.cash.surplus import compute_surplus, get_planned_upcoming_payments, get_policy

	company = company or _default_company()
	horizon_days = parse_horizon_days(horizon_days)
	as_of = today()
	# Morning planning uses yesterday's statement balances (T-1)
	bank_as_of = default_bank_statement_as_of()

	# Read-only morning view — do not sync plan from books here (slow, especially Other Site).
	# Sync stays explicit on Commitments → "Sync plan from books".

	cash = get_eligible_bank_cash(company, as_of=bank_as_of)
	surplus = compute_surplus(
		company,
		as_of=as_of,
		horizon_days=horizon_days,
		bank_cash=flt(cash.get("total")),
	)
	policy = get_policy(company)
	upcoming = get_planned_upcoming_payments(company, as_of, horizon_days)

	# Free cash = bank − commitments − policy. Incoming (Inflow/Setoff) is separate.
	def _effect(r):
		return r.get("cash_effect") or "Outflow"

	commitments = [r for r in upcoming if _effect(r) == "Outflow"]
	incoming = [r for r in upcoming if _effect(r) in ("Inflow", "Setoff")]
	commitments_total = flt(sum(flt(r.get("amount")) for r in commitments))
	incoming_total = flt(sum(flt(r.get("amount")) for r in incoming))
	incoming_expected = 0.0
	for r in incoming:
		prob = r.get("probability")
		if prob is None or prob == "":
			prob = 100
		incoming_expected += flt(r.get("amount")) * min(max(flt(prob), 0), 100) / 100.0
	incoming_expected = flt(incoming_expected)

	from lyqd.mytra.portfolio import get_portfolio

	portfolio = get_portfolio(company)
	liquid_rows = portfolio.get("positions") or []
	liquid_total = flt(portfolio.get("liquid_total") or 0)

	required = (
		flt(surplus.upcoming_total)
		+ flt(surplus.min_liquidity_buffer)
		+ flt(surplus.restricted_cash)
	)
	bank_cash = flt(cash.get("total"))
	cash_gap = max(0.0, required - bank_cash)
	redemption_need = min(cash_gap, liquid_total) if liquid_total else cash_gap

	# Open instruction is the durable intent; proposal is only its frozen snapshot.
	planned_investment = 0.0
	planned_ref = None
	planned_status = None
	planned_request_type = None
	planned_proposal = None
	open_instr = frappe.get_all(
		"LYQD Investment Instruction",
		filters={"company": company, "status": ("in", ["Draft", "Approved", "Ready"])},
		fields=["name", "amount", "status", "side", "proposal", "creation"],
		order_by="creation desc",
		limit=1,
	)
	if open_instr:
		row = open_instr[0]
		planned_investment = flt(row.amount)
		planned_ref = row.name
		planned_status = row.status
		planned_request_type = "Redeem" if (row.side or "") == "Redeem" else "Invest"
		planned_proposal = row.proposal

	# Actual free cash = position − commitments − policy (incoming excluded).
	# Expected free cash = actual + expected incoming (probability-weighted).
	signed_investable = flt(surplus.investable_surplus)
	is_shortfall = bool(surplus.is_shortfall)
	deployable = signed_investable if not is_shortfall else 0.0
	expected_free_cash = flt(signed_investable + incoming_expected)
	expected_is_shortfall = expected_free_cash < -0.01
	incoming_covers_shortfall = bool(is_shortfall and not expected_is_shortfall)

	# Drift vs open request for *this* horizon (Invest deploy vs Redeem need).
	over_allocated = 0.0
	redeem_no_longer_needed = False
	redeem_over_need = 0.0
	redeem_under_need = 0.0
	# Open Invest while this horizon is a shortfall → cancel invest, start redeem.
	invest_flipped_to_shortfall = False
	if planned_investment and planned_request_type == "Redeem":
		if not is_shortfall:
			# Horizon / balances flipped to free cash — redeem request is stale.
			redeem_no_longer_needed = True
		else:
			# Still short: open redeem vs today's need (either direction).
			delta = flt(planned_investment) - flt(redemption_need)
			if delta > 0.01:
				redeem_over_need = delta
			elif delta < -0.01:
				redeem_under_need = abs(delta)
	elif planned_investment:
		if is_shortfall:
			invest_flipped_to_shortfall = True
		else:
			# Invest still applicable: how much less can be deployed vs the open request.
			over_allocated = max(0.0, planned_investment - deployable)

	# If already sitting in liquid funds, redemption to correct an Invest plan is capped by holdings.
	plan_redemption = min(over_allocated, liquid_total) if liquid_total else 0.0

	return {
		"company": company,
		"as_of": as_of,
		"bank_as_of": bank_as_of,
		"horizon_days": horizon_days,
		"bank_cash": bank_cash,
		"banks": cash.get("accounts") or [],
		"liquid_fund_total": liquid_total,
		"liquid_holdings": liquid_rows,
		# Free-cash reserve (outflows − setoffs); never includes inflows
		"upcoming_total": flt(surplus.upcoming_total),
		# Home-page cards: commitments (outflows ≥ 0) and incoming (separate)
		"commitments_total": commitments_total,
		"incoming_total": incoming_total,
		"incoming_expected": incoming_expected,
		"upcoming": commitments,
		"incoming": incoming,
		"min_liquidity_buffer": flt(policy.get("min_liquidity_buffer")),
		"restricted_cash": flt(policy.get("restricted_cash")),
		"required_cash": required,
		"investable_surplus": signed_investable,
		"is_shortfall": is_shortfall,
		"expected_free_cash": expected_free_cash,
		"expected_is_shortfall": expected_is_shortfall,
		"incoming_covers_shortfall": incoming_covers_shortfall,
		"cash_gap": cash_gap,
		"redemption_need": redemption_need,
		"planned_investment": planned_investment,
		"planned_ref": planned_ref,
		"planned_status": planned_status,
		"planned_request_type": planned_request_type,
		"planned_proposal": planned_proposal,
		"over_allocated": over_allocated,
		"invest_flipped_to_shortfall": invest_flipped_to_shortfall,
		"redeem_no_longer_needed": redeem_no_longer_needed,
		"redeem_over_need": redeem_over_need,
		"redeem_under_need": redeem_under_need,
		"plan_redemption": plan_redemption,
		"needs_redemption": redemption_need > 0.01 or plan_redemption > 0.01,
		"has_open_request": bool(planned_ref),
	}


@frappe.whitelist()
def get_company_bank_account_options(company: str | None = None) -> dict:
	"""
	Company bank accounts for Policy / Banks selection.

	From This Site or Other Site based on the LYQD Company's books settings.
	"""
	from lyqd.cash.bank_cash import get_company_bank_accounts
	from lyqd.recommendations.settings import get_integration_settings, is_remote_source

	company = company or _default_company()
	settings = get_integration_settings(company)
	try:
		rows = get_company_bank_accounts(company)
	except Exception as e:
		frappe.log_error(title="LYQD bank account options failed")
		return {
			"source": settings.get("source") or "This Site",
			"books_company": settings.get("remote_company")
			if is_remote_source(company)
			else company,
			"accounts": [],
			"message": str(e),
			"balance_source": None,
		}

	message = None
	books_company = company
	source = "This Site"
	mirrored = None
	if is_remote_source(company):
		source = "Other Site"
		books_company = settings.get("remote_company")
		# rows already mirrored locally via get_company_bank_accounts
		if rows:
			books_company = rows[0].get("books_company") or books_company
			mirrored = {"count": len(rows)}
		else:
			url = settings.get("remote_site_url") or "the remote ERPNext site"
			message = (
				f"No company bank accounts on {url}. "
				"Add Bank Accounts there (company account = Yes), then reconnect / reload. "
				"LYQD mirrors them locally and never writes to the remote site."
			)

	return {
		"source": source,
		"books_company": books_company,
		"accounts": rows,
		"message": message,
		"balance_source": "this_site",
		"mirrored": mirrored,
		"remote_writes": False,
	}


@frappe.whitelist()
def create_surplus_bank_account(
	company: str | None = None,
	account_name: str | None = None,
	bank: str | None = None,
	opening_balance: float | None = 0,
	add_to_policy: int | bool = 1,
	account_type: str | None = None,
	is_default: int | bool = 0,
	bank_account_no: str | None = None,
) -> dict:
	"""Create LYQD Bank Account (no CoA); optionally pin on Policy."""
	from lyqd.cash.bank_cash import create_company_bank_account

	frappe.only_for(("System Manager", "LYQD Manager", "Accounts Manager"))
	return create_company_bank_account(
		company=company or _default_company(),
		account_name=account_name,
		bank=bank,
		opening_balance=flt(opening_balance),
		add_to_policy=bool(int(add_to_policy)),
		account_type=account_type,
		is_default=bool(int(is_default)),
		bank_account_no=bank_account_no,
	)


@frappe.whitelist()
def get_or_create_policy(company: str | None = None) -> dict:
	"""Return Policy tab fields for a LYQD Company (creates company defaults if needed)."""
	company = company or _default_company()
	if not company:
		frappe.throw(_("Company is required"))
	if not frappe.db.exists("LYQD Company", company):
		create_lyqd_company(company_name=company)
	doc = frappe.get_doc("LYQD Company", company)
	# Ensure policy scalars have settings defaults when blank
	if doc.default_forecast_horizon_days is None or doc.min_liquidity_buffer is None:
		doc.apply_settings_defaults()
		doc.save(ignore_permissions=True)
		doc.reload()
	return doc.as_dict()


def _set_policy_child_rows(doc, fieldname: str, key: str, rows: list, extra_keys: list | None = None) -> None:
	doc.set(fieldname, [])
	extra_keys = extra_keys or []
	for row in rows or []:
		if isinstance(row, dict):
			value = row.get(key)
			payload = {key: value}
			for ek in extra_keys:
				if ek in row:
					payload[ek] = row.get(ek)
		else:
			value = row
			payload = {key: value}
		if value:
			doc.append(fieldname, payload)


@frappe.whitelist()
def save_policy(doc: str | dict) -> dict:
	"""Persist Policy / Recommendations tab fields onto the LYQD Company."""
	if isinstance(doc, str):
		doc = frappe.parse_json(doc)
	company = (doc.get("company") or doc.get("name") or _default_company() or "").strip()
	if not company:
		frappe.throw(_("Company is required"))
	if not frappe.db.exists("LYQD Company", company):
		create_lyqd_company(company_name=company)

	existing = frappe.get_doc("LYQD Company", company)
	existing.min_liquidity_buffer = doc.get("min_liquidity_buffer")
	existing.restricted_cash = doc.get("restricted_cash")
	existing.default_forecast_horizon_days = doc.get("default_forecast_horizon_days")
	if "notes" in doc:
		existing.notes = doc.get("notes")
	if "is_active" in doc and doc.get("is_active") is not None:
		existing.is_active = doc.get("is_active")
	existing.enable_purchase_invoice_recommendations = doc.get(
		"enable_purchase_invoice_recommendations", 1
	)
	_set_policy_child_rows(
		existing,
		"eligible_bank_accounts",
		"bank_account",
		doc.get("eligible_bank_accounts") or [],
		extra_keys=["account_name", "gl_account"],
	)
	_set_policy_child_rows(
		existing,
		"recommendation_accounts",
		"account",
		doc.get("recommendation_accounts") or [],
		extra_keys=["account_name", "show_references", "parent_account"],
	)
	existing.save()
	# Create missing child Account-grain plans + nest under parents from the new config
	nested = None
	try:
		from lyqd.recommendations.core import sync_nested_account_plans

		nested = sync_nested_account_plans(existing.name)
	except Exception:
		frappe.log_error(title="LYQD sync nested account plans after policy save")
	out = existing.as_dict()
	if nested:
		out["_nested_plans"] = nested
	return out


@frappe.whitelist()
def get_recommendation_account_options(
	company: str | None = None,
	root_type: str | None = None,
	account_type: str | None = None,
	search: str | None = None,
) -> dict:
	"""
	Leaf accounts for the Integrations account picker.

	Reads from This Site (local) or Other Site (remote API) based on the LYQD Company.
	"""
	from lyqd.recommendations.settings import SOURCE_OTHER_SITE, get_integration_settings

	company = company or _default_company()
	settings = get_integration_settings(company)
	source = settings.get("source") or "This Site"
	# Liability = outflows; Asset = setoff (e.g. Input GST). Expense is not used for treasury.
	root_types = ["Liability", "Asset"]
	if root_type and root_type not in ("All", "all", ""):
		if root_type == "Expense":
			return {
				"source": source,
				"books_company": settings.get("remote_company"),
				"enabled": bool(settings.get("enabled")),
				"accounts": [],
				"message": _("Expense accounts are not used for treasury recommendations."),
			}
		root_types = [root_type]

	if settings.get("enabled") and source == SOURCE_OTHER_SITE:
		from lyqd.recommendations.remote import list_remote_recommendation_accounts

		try:
			rows = list_remote_recommendation_accounts(
				root_types=root_types,
				account_type=account_type,
				search=search,
				lyqd_company=company,
			)
		except Exception as e:
			frappe.log_error(title="LYQD remote account list failed")
			return {
				"source": source,
				"books_company": settings.get("remote_company"),
				"enabled": True,
				"accounts": [],
				"message": str(e),
			}
		return {
			"source": source,
			"books_company": settings.get("remote_company"),
			"enabled": True,
			"accounts": rows,
			"message": None,
		}

	books_company = settings.get("remote_company") or company
	filters: dict = {
		"company": books_company,
		"is_group": 0,
		"root_type": ("in", root_types),
	}
	if account_type and account_type not in ("All", "all", ""):
		filters["account_type"] = account_type

	rows = frappe.get_all(
		"Account",
		filters=filters,
		fields=["name", "account_name", "account_type", "root_type"],
		order_by="root_type asc, account_name asc",
		limit=500,
	)
	q = (search or "").strip().lower()
	if q:
		rows = [
			r
			for r in rows
			if q in (r.name or "").lower()
			or q in (r.account_name or "").lower()
			or q in (r.account_type or "").lower()
		]
	for r in rows:
		r["source"] = "This Site"
		r["books_company"] = books_company
	return {
		"source": "This Site",
		"books_company": books_company,
		"enabled": bool(settings.get("enabled")),
		"accounts": rows,
		"message": None,
	}


@frappe.whitelist()
def get_upcoming_recommendations(company: str | None = None, horizon_days: int | None = None) -> dict:
	from lyqd.recommendations import get_liability_recommendations

	return get_liability_recommendations(
		company=company or _default_company(),
		horizon_days=int(horizon_days) if horizon_days is not None else None,
	)


@frappe.whitelist()
def accept_upcoming_recommendation(
	company: str | None = None,
	source_doctype: str | None = None,
	source_name: str | None = None,
	amount: float | None = None,
	title: str | None = None,
	category: str | None = None,
	due_date: str | None = None,
	account: str | None = None,
	cash_effect: str | None = None,
	source_row: str | None = None,
	probability: float | int | None = None,
) -> dict:
	from lyqd.recommendations import accept_recommendation

	return accept_recommendation(
		company=company or _default_company(),
		source_doctype=source_doctype,
		source_name=source_name,
		amount=flt(amount) if amount is not None else None,
		title=title,
		category=category,
		due_date=due_date,
		account=account,
		cash_effect=cash_effect,
		source_row=source_row,
		probability=probability,
	)


@frappe.whitelist()
def ignore_upcoming_recommendation(
	company: str | None = None,
	source_doctype: str | None = None,
	source_name: str | None = None,
	amount: float | None = None,
	title: str | None = None,
	category: str | None = None,
	due_date: str | None = None,
	account: str | None = None,
	cash_effect: str | None = None,
	source_row: str | None = None,
) -> dict:
	"""Store an Ignored Upcoming Payment so the voucher/account leaves From-books."""
	from lyqd.recommendations import ignore_recommendation

	return ignore_recommendation(
		company=company or _default_company(),
		source_doctype=source_doctype,
		source_name=source_name,
		amount=flt(amount) if amount is not None else None,
		title=title,
		category=category,
		due_date=due_date,
		account=account,
		cash_effect=cash_effect,
		source_row=source_row,
	)


@frappe.whitelist()
def sync_upcoming_from_books(company: str | None = None) -> dict:
	"""Refresh ERPNext-sourced plan rows: amounts, Paid when cleared, Account GL balances."""
	from lyqd.recommendations import sync_planned_from_books

	return sync_planned_from_books(company or _default_company())


@frappe.whitelist()
def relink_commitment_parents(company: str | None = None) -> dict:
	"""Create missing child Account-grain plans and nest them under parent plans from Settings."""
	from lyqd.recommendations.core import sync_nested_account_plans

	company = company or _default_company()
	frappe.only_for(("System Manager", "LYQD Manager", "LYQD User"))
	result = sync_nested_account_plans(company)
	return result


@frappe.whitelist()
def refresh_upcoming_from_books(name: str) -> dict:
	"""Refresh a single Upcoming Payment from its ERPNext source."""
	from lyqd.recommendations import sync_upcoming_payment_from_books

	return sync_upcoming_payment_from_books(name)


@frappe.whitelist()
def preview_split_upcoming_payment(name: str) -> dict:
	"""Suggested Split rows (Payment Schedule when available, else current row + blank)."""
	from lyqd.recommendations import preview_split_upcoming_payment as _preview

	frappe.only_for(("System Manager", "LYQD Manager", "LYQD User"))
	return _preview(name)


@frappe.whitelist()
def split_upcoming_payment(name: str, rows: str | list | None = None) -> dict:
	"""Replace one Planned payment with N dated plan rows (generic Split)."""
	from lyqd.recommendations import split_upcoming_payment as _split

	frappe.only_for(("System Manager", "LYQD Manager", "LYQD User"))
	return _split(name, rows)


@frappe.whitelist()
def mark_upcoming_split_paid(parent: str, split_row_name: str) -> dict:
	"""Mark one GL schedule (child table) line as Paid."""
	from lyqd.recommendations.core import mark_upcoming_split_paid as _mark

	frappe.only_for(("System Manager", "LYQD Manager", "LYQD User"))
	return _mark(parent, split_row_name)


@frappe.whitelist()
def default_balance_as_of(due_date: str | None = None) -> dict:
	"""Suggested freeze date: last day of the month before the due date (GST/TDS)."""
	from lyqd.recommendations.core import default_balance_as_of_for_due

	return {"balance_as_of": default_balance_as_of_for_due(due_date)}


@frappe.whitelist()
def freeze_upcoming_balance(
	name: str,
	as_of: str | None = None,
	clear: int | bool | str | None = 0,
) -> dict:
	"""
	Freeze Account-grain plan amount to GL as of ``as_of`` (cascades to children).

	Pass clear=1 to resume live (today) balances on refresh.
	"""
	from lyqd.recommendations.core import (
		default_balance_as_of_for_due,
		set_upcoming_balance_as_of,
	)

	frappe.only_for(("System Manager", "LYQD Manager", "LYQD User"))
	doc = frappe.get_doc("LYQD Upcoming Payment", name)
	clear_flag = str(clear).lower() in ("1", "true", "yes")
	if clear_flag:
		return set_upcoming_balance_as_of(name, None, cascade_children=True, sync=True)

	as_of_s = as_of or default_balance_as_of_for_due(doc.due_date)
	return set_upcoming_balance_as_of(name, as_of_s, cascade_children=True, sync=True)


@frappe.whitelist()
def list_upcoming_payments(company: str | None = None) -> list[dict]:
	"""SPA plan list: all statuses, with Planned recurring series expanded to the policy horizon."""
	from frappe.utils import cint

	from lyqd.cash.recurring import expand_recurring_row

	company = company or _default_company()
	as_of = today()
	policy = get_policy(company)
	horizon_days = parse_horizon_days(policy.get("default_forecast_horizon_days") or 7)
	rows = frappe.get_all(
		"LYQD Upcoming Payment",
		filters={"company": company},
		fields=[
			"name",
			"title",
			"category",
			"due_date",
			"amount",
			"group_net",
			"cash_effect",
			"probability",
			"status",
			"notes",
			"company",
			"source_doctype",
			"source_name",
			"source_row",
			"source_account",
			"parent_payment",
			"balance_as_of",
			"last_synced_on",
			"is_recurring",
			"frequency",
			"recurrence_end",
		],
		order_by="due_date asc",
		limit_page_length=500,
	)
	names = [r.name for r in rows]
	splits_by_parent: dict[str, list] = {}
	if names and frappe.db.exists("DocType", "LYQD Upcoming Split"):
		for s in frappe.get_all(
			"LYQD Upcoming Split",
			filters={"parent": ("in", names)},
			fields=["name", "parent", "due_date", "amount", "title", "status", "probability", "idx"],
			order_by="due_date asc, idx asc",
		):
			splits_by_parent.setdefault(s.parent, []).append(s)

	def _signed(amount, effect):
		amt = flt(amount)
		return amt if (effect or "Outflow") == "Outflow" else -amt

	for row in rows:
		if row.get("status") == "Planned":
			expand_recurring_row(row, as_of, horizon_days)
		else:
			row["period_amount"] = flt(row.get("amount"))
			row["occurrence_count"] = 1
			row["occurrence_dates"] = [str(row["due_date"])] if row.get("due_date") else []

		kids = splits_by_parent.get(row.name) or []
		if kids:
			row["_has_splits"] = 1
			row["_children"] = [
				{
					"name": f"{row.name}::split::{s.name}",
					"split_name": s.name,
					"title": s.title or row.title,
					"due_date": s.due_date,
					"amount": flt(s.amount),
					"status": s.status or "Planned",
					"probability": (
						flt(s.probability)
						if s.probability is not None and s.probability != ""
						else (
							flt(row.probability)
							if row.probability is not None and row.probability != ""
							else 100
						)
					),
					"cash_effect": row.cash_effect,
					"category": row.category,
					"parent_payment": row.name,
					"source_doctype": row.source_doctype,
					"source_name": row.source_name,
					"_schedule": 1,
					"_child": 1,
					"_childCount": 0,
					"_children": [],
				}
				for s in kids
			]
			row["_childCount"] = len(kids)
			# Header amount already = sum of Planned lines; group net is that signed total
			row["_groupNet"] = sum(
				_signed(c["amount"], row.cash_effect)
				for c in row["_children"]
				if (c.get("status") or "Planned") == "Planned"
			)
		else:
			row["_has_splits"] = 0
	return rows


@frappe.whitelist()
def save_upcoming_payment(doc: str | dict | None = None) -> dict:
	"""Create or update an LYQD Upcoming Payment from the SPA (edit plan rows)."""
	from frappe.utils import cint

	from lyqd.cash.recurring import advance_recurring_after_paid

	if isinstance(doc, str):
		doc = frappe.parse_json(doc)
	if not doc:
		frappe.throw(_("No payment data"))

	company = doc.get("company") or _default_company()
	name = doc.get("name")
	allowed_effects = ("Outflow", "Setoff", "Inflow")

	if name:
		payment = frappe.get_doc("LYQD Upcoming Payment", name)
		if payment.company != company and company:
			# keep existing company; SPA may send current company selector
			pass
		payment.title = (doc.get("title") or payment.title or "").strip()
		payment.category = doc.get("category") or payment.category or "Other"
		has_schedule = bool(payment.get("splits"))
		# Child due dates follow parent — ignore SPA edits on nested rows.
		# Split schedules own amount / due via _sync_from_splits — ignore SPA amount.
		if not has_schedule:
			if not payment.parent_payment:
				payment.due_date = doc.get("due_date") or payment.due_date
			# Prefer period_amount when SPA sends horizon-expanded amount by mistake
			if doc.get("period_amount") is not None:
				payment.amount = flt(doc.get("period_amount"))
			else:
				payment.amount = flt(doc.get("amount"))
		# Manual rows may set Outflow/Inflow; books-sourced Setoff stays unless SPA sends effect
		if not payment.source_doctype and doc.get("cash_effect") in allowed_effects:
			payment.cash_effect = doc.get("cash_effect")
		if "is_recurring" in doc:
			payment.is_recurring = 1 if cint(doc.get("is_recurring")) else 0
		if payment.is_recurring:
			payment.frequency = doc.get("frequency") or payment.frequency or "Monthly"
			payment.recurrence_end = doc.get("recurrence_end") or None
			payment.cash_effect = "Outflow"
		elif "is_recurring" in doc:
			payment.frequency = None
			payment.recurrence_end = None
		if doc.get("status") in ("Planned", "Paid", "Cancelled", "Ignored"):
			want = doc.get("status")
			# Recurring series: "Paid" advances next due and stays Planned (like GL grain)
			if want == "Paid" and cint(payment.is_recurring):
				advance_recurring_after_paid(payment)
			elif want == "Paid" and payment.get("splits"):
				# Header Paid with a GL schedule → mark every Planned maturity Paid.
				# (status alone is overwritten by _sync_from_splits while lines stay Planned.)
				for split in payment.get("splits") or []:
					if (split.status or "Planned") == "Planned":
						split.status = "Paid"
			elif want == "Ignored" and payment.get("splits"):
				frappe.throw(
					_("Cannot ignore a payment that has a split schedule. Merge first.")
				)
			elif not has_schedule:
				payment.status = want
				# Ignored rows are not nested / do not reserve free cash
				if want == "Ignored":
					payment.parent_payment = None
		payment.notes = doc.get("notes")
		# Prefer SPA-sent effect for probability when books rows keep Setoff in DB
		# but the form remaps Setoff → Inflow for editing.
		effect_for_prob = payment.cash_effect
		if doc.get("cash_effect") in ("Inflow", "Setoff"):
			effect_for_prob = doc.get("cash_effect")
		if effect_for_prob in ("Inflow", "Setoff"):
			if "probability" in doc and not has_schedule:
				payment.probability = min(max(flt(doc.get("probability")), 0), 100)
		else:
			payment.probability = 100
		# Per-installment fields on the GL split schedule (prob / status / due)
		if has_schedule and isinstance(doc.get("splits"), (list, tuple)):
			by_name = {s.name: s for s in (payment.get("splits") or [])}
			for row in doc.get("splits") or []:
				child = by_name.get(row.get("name") or row.get("split_name"))
				if not child:
					continue
				if effect_for_prob in ("Inflow", "Setoff") and "probability" in row:
					child.probability = min(max(flt(row.get("probability")), 0), 100)
				elif effect_for_prob not in ("Inflow", "Setoff"):
					child.probability = 100
				if row.get("status") in ("Planned", "Paid"):
					child.status = row.get("status")
				# Calendar drag-reschedule / edit due on one installment
				if row.get("due_date"):
					child.due_date = getdate(row.get("due_date"))
		if not payment.title:
			frappe.throw(_("Title is required"))
		payment.save()
		return payment.as_dict()

	cash_effect = doc.get("cash_effect") if doc.get("cash_effect") in allowed_effects else "Outflow"
	is_recurring = 1 if cint(doc.get("is_recurring")) else 0
	if is_recurring:
		cash_effect = "Outflow"
	probability = 100
	if cash_effect in ("Inflow", "Setoff"):
		probability = min(max(flt(doc.get("probability") if doc.get("probability") is not None else 100), 0), 100)
	payment = frappe.get_doc(
		{
			"doctype": "LYQD Upcoming Payment",
			"company": company,
			"title": (doc.get("title") or "").strip(),
			"category": doc.get("category") or "Other",
			"due_date": doc.get("due_date") or today(),
			"amount": flt(doc.get("period_amount") if doc.get("period_amount") is not None else doc.get("amount")),
			"cash_effect": cash_effect,
			"probability": probability,
			"is_recurring": is_recurring,
			"frequency": (doc.get("frequency") or "Monthly") if is_recurring else None,
			"recurrence_end": doc.get("recurrence_end") if is_recurring else None,
			"status": doc.get("status")
			if doc.get("status") in ("Planned", "Paid", "Cancelled", "Ignored")
			else "Planned",
			"notes": doc.get("notes"),
		}
	)
	if not payment.title:
		frappe.throw(_("Title is required"))
	payment.insert()
	return payment.as_dict()


@frappe.whitelist()
def get_erpnext_settings(company: str | None = None) -> dict:
	"""Books + investment settings for one LYQD Company."""
	from lyqd.recommendations.settings import settings_for_api

	company = company or _default_company()
	return settings_for_api(company)


@frappe.whitelist()
def save_erpnext_settings(doc: str | dict) -> dict:
	"""Persist books connector fields onto the LYQD Company (not Singles)."""
	from lyqd.recommendations.settings import SOURCE_OTHER_SITE, settings_for_api

	if isinstance(doc, str):
		doc = frappe.parse_json(doc)
	frappe.only_for(("System Manager", "LYQD Manager"))

	lyqd_company = (doc.get("company") or _default_company() or "").strip()
	if not lyqd_company:
		frappe.throw(_("Company is required"))

	enabled = bool(int(doc.get("enabled") or 0))
	source = doc.get("source") or doc.get("books_source") or "This Site"
	if source not in ("This Site", "Other Site", "Manual"):
		source = "This Site"
	# SPA "enabled" off → Manual (LYQD-only balances, no recommendations)
	if not enabled:
		books_source = "Manual"
	elif source == "Other Site":
		books_source = SOURCE_OTHER_SITE
	else:
		books_source = "This Site"

	books_company = (doc.get("remote_company") or "").strip()
	if books_source in ("This Site", SOURCE_OTHER_SITE) and not books_company:
		frappe.throw(
			_(
				"Books company is required when ERPNext is enabled. "
				"Select the ERPNext Company this LYQD Company should use."
			)
		)

	if not frappe.db.exists("LYQD Company", lyqd_company):
		create_lyqd_company(
			company_name=lyqd_company,
			books_source=books_source,
			books_company=books_company,
			remote_site_url=doc.get("remote_site_url"),
			remote_api_key=doc.get("remote_api_key"),
			remote_api_secret=doc.get("remote_api_secret"),
		)

	co = frappe.get_doc("LYQD Company", lyqd_company)
	was_remote = (co.books_source or "") == SOURCE_OTHER_SITE
	co.apply_books_source(books_source)
	if books_source == SOURCE_OTHER_SITE:
		co.books_company = books_company
		co.remote_site_url = (doc.get("remote_site_url") or "").strip()
		co.remote_api_key = (doc.get("remote_api_key") or "").strip()
		new_secret = doc.get("remote_api_secret")
		if new_secret:
			co.remote_api_secret = new_secret
	elif books_source == "This Site":
		co.books_company = books_company
	co.save()

	payload = settings_for_api(lyqd_company)
	now_remote = bool(payload.get("enabled") and payload.get("source") == SOURCE_OTHER_SITE)
	if was_remote and not now_remote:
		payload["plan_note"] = (
			"Accepted plan items stay on Commitments as Planned/Paid with their source refs. "
			"Sync from books stops until Other site is enabled again. "
			"Mirrored local bank accounts and balances remain on this site."
		)
	if now_remote:
		try:
			from lyqd.cash.mirror_banks import mirror_remote_bank_accounts

			payload["bank_mirror"] = mirror_remote_bank_accounts(lyqd_company)
		except Exception as e:
			frappe.log_error(title="LYQD bank mirror on save settings")
			payload["bank_mirror_error"] = str(e)
	return payload


@frappe.whitelist()
def probe_remote_erpnext_connection(
	url: str | None = None,
	api_key: str | None = None,
	api_secret: str | None = None,
	company: str | None = None,
	lyqd_company: str | None = None,
	skip_mirror: int | bool = 0,
) -> dict:
	"""
	Validate draft remote credentials and list companies on that site.

	Uses the posted secret, or the stored secret on the LYQD Company when blank.
	``company`` is the remote books company name; ``lyqd_company`` is the local entity.
	Pass ``skip_mirror=1`` when probing before the LYQD Company exists (create dialog).
	"""
	frappe.only_for(("System Manager", "LYQD Manager", "LYQD User"))
	from lyqd.recommendations.remote import probe_remote_connection
	from lyqd.recommendations.settings import get_integration_settings

	# Only use an explicit lyqd_company for secret lookup / mirror — not a silent default
	local = (lyqd_company or "").strip()
	secret = (api_secret or "").strip()
	if not secret and local:
		s = get_integration_settings(local)
		if s.get("has_remote_api_secret") and frappe.db.exists("LYQD Company", local):
			doc = frappe.get_doc("LYQD Company", local)
			secret = doc.get_password("remote_api_secret", raise_exception=False) or ""
	result = probe_remote_connection(
		url=url or "",
		api_key=api_key or "",
		api_secret=secret,
		company=company,
	)
	# Persist resolved books company when blank on the LYQD Company
	if result.get("company") and local and frappe.db.exists("LYQD Company", local):
		doc = frappe.get_doc("LYQD Company", local)
		if (doc.books_source or "") == "Other Site" and not (doc.books_company or "").strip():
			doc.books_company = result["company"]
			doc.save(ignore_permissions=True)
	# Mirror remote banks locally (never writes to remote)
	if local and not int(skip_mirror or 0):
		try:
			from lyqd.cash.mirror_banks import mirror_remote_bank_accounts

			result["bank_mirror"] = mirror_remote_bank_accounts(local)
		except Exception as e:
			frappe.log_error(title="LYQD bank mirror on probe")
			result["bank_mirror_error"] = str(e)
	result["remote_writes"] = False
	result["lyqd_company"] = local
	return result


@frappe.whitelist()
def get_settings() -> dict:
	"""Site-wide LYQD defaults (not per-company books/investment)."""
	s = frappe.get_single("LYQD Settings")
	return s.as_dict()


@frappe.whitelist()
def save_settings(doc: str | dict) -> dict:
	if isinstance(doc, str):
		doc = frappe.parse_json(doc)
	s = frappe.get_single("LYQD Settings")
	for key in (
		"default_forecast_horizon_days",
		"default_min_liquidity_buffer",
		"default_restricted_cash",
		"in_beta",
		"tagline",
		"display_scheme_label",
		"display_scheme_isin",
		"illustrative_idle_yield_pct",
		"illustrative_fd_yield_pct",
		"illustrative_liquid_yield_pct",
	):
		if key in doc:
			val = doc.get(key)
			if key.endswith("_yield_pct") and val is not None:
				try:
					val = max(0.0, min(100.0, float(val)))
				except (TypeError, ValueError):
					continue
			s.set(key, val)
	s.save()
	return s.as_dict()


def _investment_account_active(company: str | None = None) -> bool:
	company = company or _default_company()
	if not company or not frappe.db.exists("LYQD Company", company):
		return False
	return bool(frappe.db.get_value("LYQD Company", company, "investment_account_activated"))


@frappe.whitelist()
def request_investment_account(company: str | None = None, note: str | None = None) -> dict:
	"""Stamp that the SPA opened the WhatsApp activation flow (no CRM Lead create)."""
	_ = note
	company = (company or _default_company() or "").strip()
	if not company:
		frappe.throw(_("Company is required"))
	if not frappe.db.exists("LYQD Company", company):
		frappe.throw(_("LYQD Company {0} not found").format(company))

	doc = frappe.get_doc("LYQD Company", company)
	if int(doc.investment_account_activated or 0):
		return {
			"already_activated": True,
			"requested_on": doc.investment_account_requested_on,
			"message": _("Investment account is already activated."),
		}

	already = bool(doc.investment_account_requested_on)
	if not already:
		doc.investment_account_requested_on = frappe.utils.now_datetime()
		doc.save(ignore_permissions=True)

	return {
		"already_requested": already,
		"requested_on": doc.investment_account_requested_on,
		"message": _("Activation request noted."),
	}


def _instruction_statuses_for_proposal(proposal: str) -> list[str]:
	return frappe.get_all(
		"LYQD Investment Instruction",
		filters={"proposal": proposal},
		pluck="status",
	)


def _supersede_open_investment_requests(company: str) -> list[str]:
	"""
	One open investment intent per company.

	Cancel prior Draft/Confirmed requests. Block if an Approved/Ready instruction
	is already in flight for an open request (must finish or cancel that deal first).
	Draft instructions tied to superseded requests are cancelled with them.
	"""
	cancelled: list[str] = []
	open_props = frappe.get_all(
		"LYQD Draft Proposal",
		filters={"company": company, "status": ("in", ["Draft", "Frozen"])},
		pluck="name",
		order_by="creation asc",
	)
	for name in open_props:
		statuses = _instruction_statuses_for_proposal(name)
		if any(s in ("Approved", "Ready") for s in statuses):
			frappe.throw(
				_(
					"Investment request {0} already has an Approved/Ready instruction. "
					"Finish or cancel that instruction before creating a new request."
				).format(name)
			)
		for instr in frappe.get_all(
			"LYQD Investment Instruction",
			filters={"proposal": name, "status": "Draft"},
			pluck="name",
		):
			frappe.db.set_value("LYQD Investment Instruction", instr, "status", "Cancelled")
		frappe.db.set_value(
			"LYQD Draft Proposal",
			name,
			{
				"status": "Cancelled",
				"notes": _("Superseded by a newer investment request"),
			},
		)
		cancelled.append(name)
	return cancelled


def _scheme_from_largest_holding(company: str) -> tuple[str | None, str | None]:
	from lyqd.mytra.portfolio import get_portfolio

	positions = get_portfolio(company).get("positions") or []
	if not positions:
		return None, None
	best = max(positions, key=lambda p: flt(p.get("amount") or 0))
	isin = best.get("scheme_isin") or best.get("scheme")
	label = best.get("scheme_label") or best.get("scheme")
	return label, isin


def _liquid_holdings_total(company: str) -> float:
	from lyqd.mytra.portfolio import get_portfolio

	return flt(get_portfolio(company).get("liquid_total") or 0)


def _open_instruction_for_company(company: str) -> dict | None:
	rows = frappe.get_all(
		"LYQD Investment Instruction",
		filters={"company": company, "status": ("in", ["Draft", "Approved", "Ready"])},
		fields=[
			"name",
			"status",
			"side",
			"amount",
			"proposal",
			"surplus_run",
			"as_of",
			"horizon_days",
			"scheme_label",
			"scheme_isin",
			"notes",
		],
		order_by="creation desc",
		limit=1,
	)
	return rows[0] if rows else None


def _assert_no_open_instruction(company: str) -> None:
	existing = _open_instruction_for_company(company)
	if existing:
		frappe.throw(
			_(
				"Instruction {0} is already open ({1}). Finish or cancel it on Instructions "
				"before creating another."
			).format(existing.name, existing.status)
		)


def _build_instruction_from_proposal(prop) -> dict:
	"""Insert Draft instruction linked to a Frozen proposal snapshot."""
	if not _investment_account_active(prop.company):
		frappe.throw(
			_(
				"Investment account is not activated. Open Settings → Investment account "
				"to activate it, or create a CRM request to open the account."
			)
		)
	if prop.status == "Cancelled":
		frappe.throw(_("Cannot create an instruction from a cancelled snapshot."))
	if prop.status != "Frozen":
		frappe.throw(_("Snapshot must be Frozen before creating an instruction."))
	if flt(prop.proposed_amount) <= 0.01:
		frappe.throw(_("Cannot create an instruction for a zero amount."))
	if not prop.surplus_run:
		frappe.throw(_("Snapshot is missing a Surplus Run."))
	existing = frappe.db.exists(
		"LYQD Investment Instruction",
		{"proposal": prop.name, "status": ("in", ["Draft", "Approved", "Ready"])},
	)
	if existing:
		frappe.throw(
			_("Instruction {0} already exists for this snapshot. Open Instructions to continue.").format(
				existing
			)
		)
	settings = frappe.get_single("LYQD Settings")
	scheme_isin = (
		prop.display_scheme_isin or settings.display_scheme_isin or "INF109K01VQ1"
	)
	scheme_label = (
		prop.display_scheme_label
		or settings.display_scheme_label
		or "ICICI Prudential Liquid Fund"
	)
	request_type = prop.request_type or "Invest"
	side = "Redeem" if request_type == "Redeem" else "Purchase"
	doc = frappe.get_doc(
		{
			"doctype": "LYQD Investment Instruction",
			"company": prop.company,
			"status": "Draft",
			"side": side,
			"scheme": scheme_isin,
			"scheme_isin": scheme_isin,
			"scheme_label": scheme_label,
			"amount": prop.proposed_amount,
			"as_of": prop.as_of,
			"horizon_days": prop.horizon_days,
			"proposal": prop.name,
			"surplus_run": prop.surplus_run,
			"notes": _("Created from live {0} proposal snapshot").format(request_type),
		}
	)
	doc.insert()
	return doc.as_dict()


@frappe.whitelist()
def create_instruction_from_proposal(proposal: str) -> dict:
	"""Desk / legacy: create instruction from an existing Frozen proposal snapshot."""
	prop = frappe.get_doc("LYQD Draft Proposal", proposal)
	_assert_no_open_instruction(prop.company)
	return _build_instruction_from_proposal(prop)


@frappe.whitelist()
def create_instruction_from_live(
	company: str | None = None,
	horizon_days: int | str = 7,
	request_type: str | None = "Invest",
) -> dict:
	"""Live Proposal → atomic Frozen snapshot + Draft instruction.

	Proposal page stays live; the Draft Proposal row is only the audit snapshot
	linked to the instruction.
	"""
	company = company or _default_company()
	request_type = (request_type or "Invest").strip() or "Invest"
	if request_type not in ("Invest", "Redeem"):
		frappe.throw(_("request_type must be Invest or Redeem"))

	_assert_no_open_instruction(company)

	horizon_days = parse_horizon_days(horizon_days)
	run = create_surplus_run_doc(company=company, horizon_days=horizon_days)

	if request_type == "Invest":
		if run.is_shortfall:
			if not getattr(run.flags, "reused", False):
				frappe.delete_doc("LYQD Surplus Run", run.name, force=1, ignore_permissions=True)
			frappe.throw(_("No free cash to invest for this horizon (liquidity shortfall)."))
		amount = flt(run.investable_surplus)
		if amount <= 0.01:
			if not getattr(run.flags, "reused", False):
				frappe.delete_doc("LYQD Surplus Run", run.name, force=1, ignore_permissions=True)
			frappe.throw(_("No free cash to invest for this horizon (amount is zero)."))
		scheme_label = None
		scheme_isin = None
	else:
		if not run.is_shortfall:
			frappe.throw(_("No liquidity shortfall for this horizon — use Invest instead."))
		shortfall = abs(flt(run.investable_surplus))
		liquid_total = _liquid_holdings_total(company)
		amount = min(shortfall, liquid_total) if liquid_total else 0.0
		if amount <= 0.01:
			frappe.throw(
				_(
					"No liquid fund holdings to redeem. Top up the bank from elsewhere, "
					"or wait until holdings are available on Portfolio."
				)
			)
		scheme_label, scheme_isin = _scheme_from_largest_holding(company)

	settings = frappe.get_single("LYQD Settings")
	if not scheme_label:
		scheme_label = settings.display_scheme_label
	if not scheme_isin:
		scheme_isin = settings.display_scheme_isin

	# Drop orphan Draft/Frozen snapshots that never became instructions
	superseded = _supersede_open_investment_requests(company)

	prop = frappe.get_doc(
		{
			"doctype": "LYQD Draft Proposal",
			"company": company,
			"status": "Frozen",
			"request_type": request_type,
			"surplus_run": run.name,
			"horizon_days": run.horizon_days,
			"as_of": run.as_of,
			"display_scheme_label": scheme_label,
			"display_scheme_isin": scheme_isin,
			"notes": (
				_("Snapshot for instruction · replaced {0}").format(", ".join(superseded))
				if superseded
				else _("Snapshot for instruction")
			),
		}
	)
	prop.apply_surplus_run(run, proposed_amount=amount)
	prop.status = "Frozen"
	prop.insert()

	instruction = _build_instruction_from_proposal(prop)
	out = {
		"instruction": instruction,
		"proposal": prop.as_dict(),
		"superseded": superseded,
		"surplus_run_reused": bool(getattr(run.flags, "reused", False)),
	}
	if request_type == "Redeem":
		out["redemption_need"] = amount
		out["liquid_total"] = _liquid_holdings_total(company)
		out["shortfall"] = abs(flt(run.investable_surplus))
	return out


@frappe.whitelist()
def get_open_instruction(company: str | None = None) -> dict | None:
	"""Return the company's open investment instruction + linked snapshot, if any."""
	company = company or _default_company()
	row = _open_instruction_for_company(company)
	if not row:
		return None
	out = dict(row)
	if row.proposal and frappe.db.exists("LYQD Draft Proposal", row.proposal):
		out["proposal_doc"] = frappe.get_doc("LYQD Draft Proposal", row.proposal).as_dict()
	return out


@frappe.whitelist()
def instruction_action(name: str, action: str) -> dict:
	doc = frappe.get_doc("LYQD Investment Instruction", name)
	if action == "approve":
		doc.mark_approved()
	elif action == "ready":
		doc.mark_ready()
	elif action == "submit":
		return doc.submit_to_mytra()
	else:
		frappe.throw(_("Unknown action: {0}").format(action))
	doc.reload()
	return doc.as_dict()


@frappe.whitelist()
def get_portfolio(company: str | None = None) -> dict:
	"""Portfolio positions + transaction history (Mytra-backed; local instruction bridge)."""
	from lyqd.mytra.portfolio import get_portfolio as _portfolio

	return _portfolio(company or _default_company())


@frappe.whitelist(allow_guest=True)
def get_pwa_manifest():
	"""Web app manifest for installing LYQD as a PWA (LMS-style)."""
	import json

	from werkzeug.wrappers import Response

	title = frappe.db.get_single_value("Website Settings", "app_name") or "LYQD by Mytra"
	# Prefer product name when Website Settings still says the site/desk title.
	if title in ("Frappe", "ERPNext") or not title:
		title = "LYQD by Mytra"
	short = "LYQD" if len(title) > 12 else title
	route = "/lyqd"
	# Bump when icons change so installed PWAs / browsers pick up the new mark.
	icon_v = "4"
	icon_192 = f"/assets/lyqd/manifest/manifest-icon-192.maskable.png?v={icon_v}"
	icon_512 = f"/assets/lyqd/manifest/manifest-icon-512.maskable.png?v={icon_v}"
	manifest = {
		"id": route,
		"name": title if "LYQD" in title else "LYQD by Mytra",
		"short_name": short if "LYQD" in short else "LYQD",
		"description": "Know what cash you can invest — and when you’ll need it.",
		"start_url": f"{route}/",
		"scope": f"{route}/",
		"display": "standalone",
		"orientation": "any",
		"theme_color": "#61d3a0",
		"background_color": "#61d3a0",
		"icons": [
			{
				"src": icon_192,
				"sizes": "192x192",
				"type": "image/png",
				"purpose": "any",
			},
			{
				"src": icon_512,
				"sizes": "512x512",
				"type": "image/png",
				"purpose": "any",
			},
			{
				"src": icon_512,
				"sizes": "512x512",
				"type": "image/png",
				"purpose": "maskable",
			},
		],
	}
	resp = Response(json.dumps(manifest), status=200, content_type="application/manifest+json")
	resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
	return resp
