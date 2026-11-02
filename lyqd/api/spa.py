"""Whitelisted APIs for the LYQD Vue SPA at /lyqd."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from lyqd.api.dashboard import _default_company, get_dashboard_metrics, get_surplus_explanation, save_surplus_run
from lyqd.cash.bank_cash import get_eligible_bank_cash
from lyqd.cash.surplus import compute_surplus, get_policy, parse_horizon_days
from lyqd.setup.permissions import get_user_companies


@frappe.whitelist()
def get_boot_data() -> dict:
	companies = get_user_companies() or frappe.get_all("Company", pluck="name", order_by="name asc")
	default_company = frappe.defaults.get_user_default("Company") or (companies[0] if companies else None)
	settings = {}
	if frappe.db.exists("DocType", "LYQD Settings"):
		s = frappe.get_single("LYQD Settings")
		settings = {
			"investment_account_activated": int(s.investment_account_activated or 0),
			"investment_account_crm_lead": s.investment_account_crm_lead,
			"investment_account_requested_on": s.investment_account_requested_on,
			"default_forecast_horizon_days": s.default_forecast_horizon_days,
			"enable_draft_proposals": s.enable_draft_proposals,
			"tagline": s.tagline,
			"display_scheme_label": s.display_scheme_label,
			"display_scheme_isin": s.display_scheme_isin,
		}
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
		"erpnext_integration_enabled": bool(
			frappe.db.exists("DocType", "LYQD ERPNext Settings")
			and frappe.db.get_single_value("LYQD ERPNext Settings", "enabled")
		),
	}


@frappe.whitelist()
def get_companies() -> list[str]:
	return get_user_companies() or frappe.get_all("Company", pluck="name", order_by="name asc")


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
	"""Write today's (or as_of) statement closing — Bank Account Balance only (Banking path)."""
	from lyqd.cash.bank_cash import set_statement_balance
	from lyqd.recommendations.settings import is_remote_source

	# Balances always write on this site (Other Site is read-only).
	if not frappe.has_permission("Bank Account", "write", doc=bank_account):
		frappe.only_for(("System Manager", "LYQD Manager", "Accounts Manager", "Accounts User"))
	return set_statement_balance(bank_account, flt(balance), as_of)


@frappe.whitelist()
def get_morning_mis(company: str | None = None, horizon_days: int | str = 7) -> dict:
	"""Morning MIS: bank balances (BAB), liquid holdings, upcoming, redemption need."""
	from frappe.utils import today

	from lyqd.cash.bank_cash import get_eligible_bank_cash
	from lyqd.cash.surplus import compute_surplus, get_planned_upcoming_payments, get_policy

	company = company or _default_company()
	horizon_days = parse_horizon_days(horizon_days)
	as_of = today()

	# Read-only morning view — do not sync plan from books here (slow, especially Other Site).
	# Sync stays explicit on Commitments → "Sync plan from books".

	cash = get_eligible_bank_cash(company, as_of=as_of)
	surplus = compute_surplus(company, as_of=as_of, horizon_days=horizon_days)
	policy = get_policy(company)
	upcoming = get_planned_upcoming_payments(company, as_of, horizon_days)

	holdings = frappe.get_all(
		"LYQD Holding",
		filters={"company": company},
		fields=["name", "scheme", "as_on", "units", "amount", "source"],
		order_by="as_on desc",
		limit=50,
	)
	# Latest amount per scheme (simple PoC)
	latest_by_scheme: dict[str, dict] = {}
	for h in holdings:
		if h.scheme not in latest_by_scheme:
			latest_by_scheme[h.scheme] = h
	liquid_rows = list(latest_by_scheme.values())
	liquid_total = flt(sum(flt(r.amount) for r in liquid_rows))

	required = (
		flt(surplus.upcoming_total)
		+ flt(surplus.min_liquidity_buffer)
		+ flt(surplus.restricted_cash)
	)
	bank_cash = flt(cash.get("total"))
	cash_gap = max(0.0, required - bank_cash)
	redemption_need = min(cash_gap, liquid_total) if liquid_total else cash_gap

	# Only open investment requests — Cancelled must not compare vs free cash
	planned_investment = 0.0
	planned_ref = None
	planned_status = None
	proposal = frappe.get_all(
		"LYQD Draft Proposal",
		filters={"company": company, "status": ("in", ["Draft", "Frozen"])},
		fields=["name", "proposed_amount", "status", "creation"],
		order_by="creation desc",
		limit=1,
	)
	if proposal:
		planned_investment = flt(proposal[0].proposed_amount)
		planned_ref = proposal[0].name
		planned_status = proposal[0].status

	current_investable = flt(surplus.investable_surplus) if not surplus.is_shortfall else 0.0
	# Daily bank drift vs original plan: how much less can be invested today.
	over_allocated = (
		max(0.0, planned_investment - current_investable) if planned_investment else 0.0
	)
	# If already sitting in liquid funds, redemption to correct the plan is capped by holdings.
	plan_redemption = min(over_allocated, liquid_total) if liquid_total else 0.0

	return {
		"company": company,
		"as_of": as_of,
		"horizon_days": horizon_days,
		"bank_cash": bank_cash,
		"banks": cash.get("accounts") or [],
		"liquid_fund_total": liquid_total,
		"liquid_holdings": liquid_rows,
		"upcoming_total": flt(surplus.upcoming_total),
		"upcoming": upcoming,
		"min_liquidity_buffer": flt(policy.get("min_liquidity_buffer")),
		"restricted_cash": flt(policy.get("restricted_cash")),
		"required_cash": required,
		"investable_surplus": current_investable,
		"is_shortfall": bool(surplus.is_shortfall),
		"cash_gap": cash_gap,
		"redemption_need": redemption_need,
		"planned_investment": planned_investment,
		"planned_ref": planned_ref,
		"planned_status": planned_status,
		"over_allocated": over_allocated,
		"plan_redemption": plan_redemption,
		"needs_redemption": redemption_need > 0.01 or plan_redemption > 0.01,
	}


@frappe.whitelist()
def get_company_bank_account_options(company: str | None = None) -> dict:
	"""
	Company bank accounts for Policy / Banks selection.

	From This Site or Other Site based on LYQD ERPNext Settings.
	"""
	from lyqd.cash.bank_cash import get_company_bank_accounts
	from lyqd.recommendations.settings import get_integration_settings, is_remote_source

	company = company or _default_company()
	settings = get_integration_settings()
	try:
		rows = get_company_bank_accounts(company)
	except Exception as e:
		frappe.log_error(title="LYQD bank account options failed")
		return {
			"source": settings.get("source") or "This Site",
			"books_company": settings.get("remote_company") if is_remote_source() else company,
			"accounts": [],
			"message": str(e),
			"balance_source": None,
		}

	message = None
	books_company = company
	source = "This Site"
	mirrored = None
	if is_remote_source():
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
	"""Create CoA Account + Bank Account (Banking/Plaid pattern); optionally pin on Policy."""
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
	company = company or _default_company()
	name = frappe.db.get_value("LYQD Policy", {"company": company})
	if name:
		return frappe.get_doc("LYQD Policy", name).as_dict()
	settings = frappe.get_single("LYQD Settings")
	doc = frappe.get_doc(
		{
			"doctype": "LYQD Policy",
			"company": company,
			"min_liquidity_buffer": flt(settings.default_min_liquidity_buffer),
			"restricted_cash": flt(settings.default_restricted_cash),
			"default_forecast_horizon_days": int(settings.default_forecast_horizon_days or 7),
			"is_active": 1,
		}
	)
	doc.insert()
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
	if isinstance(doc, str):
		doc = frappe.parse_json(doc)
	name = doc.get("name")
	bank_rows = doc.get("eligible_bank_accounts") or []
	rec_rows = doc.get("recommendation_accounts") or []
	scalar = {
		"min_liquidity_buffer": doc.get("min_liquidity_buffer"),
		"restricted_cash": doc.get("restricted_cash"),
		"default_forecast_horizon_days": doc.get("default_forecast_horizon_days"),
		"is_active": doc.get("is_active", 1),
		"notes": doc.get("notes"),
		"enable_purchase_invoice_recommendations": doc.get(
			"enable_purchase_invoice_recommendations", 1
		),
	}
	if name and frappe.db.exists("LYQD Policy", name):
		existing = frappe.get_doc("LYQD Policy", name)
		existing.update(scalar)
		_set_policy_child_rows(
			existing,
			"eligible_bank_accounts",
			"bank_account",
			bank_rows,
			extra_keys=["account_name", "gl_account"],
		)
		_set_policy_child_rows(
			existing,
			"recommendation_accounts",
			"account",
			rec_rows,
			extra_keys=["account_name", "show_references"],
		)
		existing.save()
		return existing.as_dict()

	payload = {
		k: v
		for k, v in doc.items()
		if k not in ("eligible_bank_accounts", "recommendation_accounts")
	}
	created = frappe.get_doc({"doctype": "LYQD Policy", **payload})
	_set_policy_child_rows(
		created,
		"eligible_bank_accounts",
		"bank_account",
		bank_rows,
		extra_keys=["account_name", "gl_account"],
	)
	_set_policy_child_rows(
		created,
		"recommendation_accounts",
		"account",
		rec_rows,
		extra_keys=["account_name", "show_references"],
	)
	created.insert()
	return created.as_dict()


@frappe.whitelist()
def get_recommendation_account_options(
	company: str | None = None,
	root_type: str | None = None,
	account_type: str | None = None,
	search: str | None = None,
) -> dict:
	"""
	Leaf accounts for the Integrations account picker.

	Reads from This Site (local) or Other Site (remote API) based on LYQD ERPNext Settings.
	"""
	from lyqd.recommendations.settings import SOURCE_OTHER_SITE, get_integration_settings

	company = company or _default_company()
	settings = get_integration_settings()
	source = settings.get("source") or "This Site"
	# Asset = setoff accounts (e.g. Input GST); Liability/Expense = outflows
	root_types = ["Liability", "Expense", "Asset"]
	if root_type and root_type not in ("All", "all", ""):
		root_types = [root_type]

	if settings.get("enabled") and source == SOURCE_OTHER_SITE:
		from lyqd.recommendations.remote import list_remote_recommendation_accounts

		try:
			rows = list_remote_recommendation_accounts(
				root_types=root_types,
				account_type=account_type,
				search=search,
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

	filters: dict = {
		"company": company,
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
		r["books_company"] = company
	return {
		"source": "This Site",
		"books_company": company,
		"enabled": bool(settings.get("enabled")),
		"accounts": rows,
		"message": None,
	}


@frappe.whitelist()
def get_upcoming_recommendations(company: str | None = None, horizon_days: int | None = None) -> dict:
	from lyqd.cash.recommendations import get_liability_recommendations

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
) -> dict:
	from lyqd.cash.recommendations import accept_recommendation

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
	)


@frappe.whitelist()
def sync_upcoming_from_books(company: str | None = None) -> dict:
	"""Refresh ERPNext-sourced plan rows: amounts, Paid when cleared, Account GL balances."""
	from lyqd.cash.recommendations import sync_planned_from_books

	return sync_planned_from_books(company or _default_company())


@frappe.whitelist()
def refresh_upcoming_from_books(name: str) -> dict:
	"""Refresh a single Upcoming Payment from its ERPNext source."""
	from lyqd.cash.recommendations import sync_upcoming_payment_from_books

	return sync_upcoming_payment_from_books(name)


@frappe.whitelist()
def save_upcoming_payment(doc: str | dict | None = None) -> dict:
	"""Create or update an LYQD Upcoming Payment from the SPA (edit plan rows)."""
	if isinstance(doc, str):
		doc = frappe.parse_json(doc)
	if not doc:
		frappe.throw(_("No payment data"))

	company = doc.get("company") or _default_company()
	name = doc.get("name")

	if name:
		payment = frappe.get_doc("LYQD Upcoming Payment", name)
		if payment.company != company and company:
			# keep existing company; SPA may send current company selector
			pass
		payment.title = (doc.get("title") or payment.title or "").strip()
		payment.category = doc.get("category") or payment.category or "Other"
		payment.due_date = doc.get("due_date") or payment.due_date
		payment.amount = flt(doc.get("amount"))
		if doc.get("cash_effect") in ("Outflow", "Setoff"):
			payment.cash_effect = doc.get("cash_effect")
		if doc.get("status") in ("Planned", "Paid", "Cancelled"):
			payment.status = doc.get("status")
		payment.notes = doc.get("notes")
		if not payment.title:
			frappe.throw(_("Title is required"))
		payment.save()
		return payment.as_dict()

	payment = frappe.get_doc(
		{
			"doctype": "LYQD Upcoming Payment",
			"company": company,
			"title": (doc.get("title") or "").strip(),
			"category": doc.get("category") or "Other",
			"due_date": doc.get("due_date") or today(),
			"amount": flt(doc.get("amount")),
			"cash_effect": doc.get("cash_effect")
			if doc.get("cash_effect") in ("Outflow", "Setoff")
			else "Outflow",
			"status": doc.get("status") if doc.get("status") in ("Planned", "Paid", "Cancelled") else "Planned",
			"notes": doc.get("notes"),
		}
	)
	if not payment.title:
		frappe.throw(_("Title is required"))
	payment.insert()
	return payment.as_dict()


@frappe.whitelist()
def get_erpnext_settings() -> dict:
	from lyqd.recommendations.settings import settings_for_api

	return settings_for_api()


@frappe.whitelist()
def save_erpnext_settings(doc: str | dict) -> dict:
	from lyqd.recommendations.settings import settings_for_api

	if isinstance(doc, str):
		doc = frappe.parse_json(doc)
	frappe.only_for(("System Manager", "LYQD Manager"))
	s = frappe.get_single("LYQD ERPNext Settings")
	was_remote = bool(s.enabled and (s.source or "") == "Other Site")
	s.enabled = 1 if doc.get("enabled") else 0
	source = doc.get("source") or "This Site"
	if source not in ("This Site", "Other Site"):
		source = "This Site"
	s.source = source
	if source == "Other Site":
		s.remote_site_url = (doc.get("remote_site_url") or "").strip()
		s.remote_company = (doc.get("remote_company") or "").strip()
		s.remote_api_key = (doc.get("remote_api_key") or "").strip()
		# Keep existing secret if the SPA sends blank (user did not rotate it)
		new_secret = doc.get("remote_api_secret")
		if new_secret:
			s.remote_api_secret = new_secret
	else:
		# Clear remote fields when switching back to this site (keep secret stored but unused)
		pass
	s.save()

	payload = settings_for_api()
	now_remote = bool(payload.get("enabled") and payload.get("source") == "Other Site")
	if was_remote and not now_remote:
		payload["plan_note"] = (
			"Accepted plan items stay on Commitments as Planned/Paid with their source refs. "
			"Sync from books stops until Other site is enabled again. "
			"Mirrored local bank accounts and balances remain on this site."
		)
	# Mirror banks when enabling Other Site (read remote → create local)
	if now_remote:
		try:
			from lyqd.cash.mirror_banks import mirror_remote_bank_accounts

			payload["bank_mirror"] = mirror_remote_bank_accounts(
				doc.get("company") or _default_company()
			)
		except Exception as e:
			frappe.log_error(title="LYQD bank mirror on save settings")
			payload["bank_mirror_error"] = str(e)
	return payload


@frappe.whitelist()
def test_remote_erpnext_connection() -> dict:
	"""Ping saved Other Site credentials."""
	frappe.only_for(("System Manager", "LYQD Manager"))
	from lyqd.recommendations.remote import test_remote_connection

	return test_remote_connection()


@frappe.whitelist()
def probe_remote_erpnext_connection(
	url: str | None = None,
	api_key: str | None = None,
	api_secret: str | None = None,
	company: str | None = None,
) -> dict:
	"""
	Validate draft remote credentials and list companies on that site.

	Uses the posted secret, or the stored secret when api_secret is blank.
	Auto-resolves company when omitted (Global Defaults / sole company).
	"""
	frappe.only_for(("System Manager", "LYQD Manager"))
	from lyqd.recommendations.remote import probe_remote_connection
	from lyqd.recommendations.settings import get_integration_settings

	secret = (api_secret or "").strip()
	if not secret:
		s = get_integration_settings()
		if s.get("has_remote_api_secret") and frappe.db.exists("DocType", "LYQD ERPNext Settings"):
			doc = frappe.get_single("LYQD ERPNext Settings")
			secret = doc.get_password("remote_api_secret", raise_exception=False) or ""
	result = probe_remote_connection(
		url=url or "",
		api_key=api_key or "",
		api_secret=secret,
		company=company,
	)
	# Persist resolved company onto settings if Other Site is already enabled
	if result.get("company") and frappe.db.exists("DocType", "LYQD ERPNext Settings"):
		doc = frappe.get_single("LYQD ERPNext Settings")
		if doc.enabled and doc.source == "Other Site" and doc.remote_company != result["company"]:
			# Only auto-write when blank so an explicit pick is kept
			if not (doc.remote_company or "").strip():
				doc.remote_company = result["company"]
				doc.save(ignore_permissions=True)
	# Mirror remote banks locally (never writes to remote)
	try:
		from lyqd.cash.mirror_banks import mirror_remote_bank_accounts

		result["bank_mirror"] = mirror_remote_bank_accounts(_default_company())
	except Exception as e:
		frappe.log_error(title="LYQD bank mirror on probe")
		result["bank_mirror_error"] = str(e)
	result["remote_writes"] = False
	return result


@frappe.whitelist()
def get_settings() -> dict:
	s = frappe.get_single("LYQD Settings")
	return s.as_dict()


@frappe.whitelist()
def save_settings(doc: str | dict) -> dict:
	if isinstance(doc, str):
		doc = frappe.parse_json(doc)
	s = frappe.get_single("LYQD Settings")
	for key in (
		"investment_account_activated",
		"default_forecast_horizon_days",
		"default_min_liquidity_buffer",
		"default_restricted_cash",
		"enable_draft_proposals",
		"tagline",
		"display_scheme_label",
		"display_scheme_isin",
	):
		if key in doc:
			s.set(key, doc.get(key))
	s.save()
	return s.as_dict()


def _investment_account_active() -> bool:
	if not frappe.db.exists("DocType", "LYQD Settings"):
		return False
	return bool(frappe.db.get_single_value("LYQD Settings", "investment_account_activated"))


@frappe.whitelist()
def request_investment_account(company: str | None = None, note: str | None = None) -> dict:
	"""Create a CRM Lead to open an investment account when activation is off."""
	if not frappe.db.exists("DocType", "CRM Lead"):
		frappe.throw(_("Install the CRM app to request an investment account opening."))

	settings = frappe.get_single("LYQD Settings")
	if int(settings.investment_account_activated or 0):
		frappe.throw(_("Investment account is already activated."))

	existing = (settings.investment_account_crm_lead or "").strip()
	if existing and frappe.db.exists("CRM Lead", existing):
		return {
			"lead": existing,
			"already_requested": True,
			"requested_on": settings.investment_account_requested_on,
			"message": _("A CRM request already exists: {0}").format(existing),
		}

	company = company or _default_company()
	user = frappe.session.user
	fullname = frappe.utils.get_fullname(user) or user
	parts = fullname.split(None, 1)
	first_name = parts[0]
	last_name = parts[1] if len(parts) > 1 else ""
	email = frappe.db.get_value("User", user, "email")

	lead_kwargs = {
		"doctype": "CRM Lead",
		"first_name": first_name,
		"last_name": last_name,
		"email": email,
		"organization": company or "",
		"status": "New",
		"job_title": _("Investment account opening (LYQD)"),
	}
	if frappe.db.exists("CRM Lead Source", "LYQD"):
		lead_kwargs["source"] = "LYQD"
	elif frappe.db.exists("DocType", "CRM Lead Source"):
		# Prefer any existing source named Website / Other; else omit
		for candidate in ("Website", "Other", "Referral"):
			if frappe.db.exists("CRM Lead Source", candidate):
				lead_kwargs["source"] = candidate
				break

	lead = frappe.get_doc(lead_kwargs)
	lead.insert()

	detail = note or _(
		"LYQD request to open an investment account for company {0}. "
		"Once opened, mark Investment Account Activated in LYQD Settings."
	).format(company or _("(site)"))
	lead.add_comment("Comment", text=detail)

	settings.investment_account_crm_lead = lead.name
	settings.investment_account_requested_on = frappe.utils.now_datetime()
	settings.save()

	return {
		"lead": lead.name,
		"already_requested": False,
		"requested_on": settings.investment_account_requested_on,
		"message": _("CRM Lead {0} created for investment account opening.").format(lead.name),
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


@frappe.whitelist()
def create_proposal_from_surplus(
	company: str | None = None,
	horizon_days: int | str = 7,
	freeze: int | str = 1,
) -> dict:
	"""Create today's investment request; supersedes any prior open request for the company."""
	company = company or _default_company()
	horizon_days = parse_horizon_days(horizon_days)
	result = compute_surplus(company, horizon_days=horizon_days)
	if result.is_shortfall:
		frappe.throw(_("No free cash to invest for this horizon (liquidity shortfall)."))

	superseded = _supersede_open_investment_requests(company)

	settings = frappe.get_single("LYQD Settings")
	doc = frappe.get_doc(
		{
			"doctype": "LYQD Draft Proposal",
			"company": company,
			"status": "Draft",
			"as_of": result.as_of,
			"horizon_days": result.horizon_days,
			"bank_cash": result.bank_cash,
			"upcoming_total": result.upcoming_total,
			"min_liquidity_buffer": result.min_liquidity_buffer,
			"restricted_cash": result.restricted_cash,
			"proposed_amount": result.investable_surplus,
			"display_scheme_label": settings.display_scheme_label,
			"display_scheme_isin": settings.display_scheme_isin,
			"frozen_explanation": frappe.as_json(result.as_dict()),
			"notes": (
				_("Replaces {0}").format(", ".join(superseded)) if superseded else None
			),
		}
	)
	doc.insert()
	if int(freeze or 0):
		doc.freeze_from_surplus()
		doc.reload()
	out = doc.as_dict()
	out["superseded"] = superseded
	return out


@frappe.whitelist()
def create_instruction_from_proposal(proposal: str) -> dict:
	if not _investment_account_active():
		frappe.throw(
			_(
				"Investment account is not activated. Open Settings → Investment account "
				"to activate it, or create a CRM request to open the account."
			)
		)
	prop = frappe.get_doc("LYQD Draft Proposal", proposal)
	if prop.status == "Cancelled":
		frappe.throw(_("Cannot create an instruction from a cancelled investment request."))
	if prop.status != "Frozen":
		frappe.throw(_("Confirm the investment request before creating an instruction."))
	existing = frappe.db.exists(
		"LYQD Investment Instruction",
		{"proposal": proposal, "status": ("in", ["Draft", "Approved", "Ready"])},
	)
	if existing:
		frappe.throw(
			_("Instruction {0} already exists for this request. Open Instructions to continue.").format(
				existing
			)
		)
	scheme = frappe.db.get_value("LYQD Scheme", {"is_default": 1, "is_active": 1}) or frappe.db.get_value(
		"LYQD Scheme", {"isin": prop.display_scheme_isin or "INF109K01VQ1"}
	)
	if not scheme:
		frappe.throw(_("No LYQD Scheme found. Seed schemes or create one in Settings / Schemes."))
	doc = frappe.get_doc(
		{
			"doctype": "LYQD Investment Instruction",
			"company": prop.company,
			"status": "Draft",
			"scheme": scheme,
			"amount": prop.proposed_amount,
			"as_of": prop.as_of,
			"horizon_days": prop.horizon_days,
			"proposal": prop.name,
			"surplus_run": prop.surplus_run,
			"notes": "Created from investment request (PoC — no external submit)",
		}
	)
	doc.insert()
	return doc.as_dict()


@frappe.whitelist()
def freeze_proposal(name: str) -> dict:
	doc = frappe.get_doc("LYQD Draft Proposal", name)
	doc.freeze_from_surplus()
	doc.reload()
	return doc.as_dict()


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
def ensure_default_schemes() -> list[dict]:
	"""Idempotent PoC catalogue (display-only)."""
	defaults = [
		{
			"isin": "INF109K01VQ1",
			"scheme_name": "ICICI Prudential Liquid Fund",
			"amc": "ICICI Prudential",
			"category": "Liquid",
			"is_default": 1,
			"is_active": 1,
			"description": "PoC default scheme — display only; no BSE fetch.",
		},
		{
			"isin": "INF204KB1ZH5",
			"scheme_name": "Nippon India Liquid Fund",
			"amc": "Nippon India",
			"category": "Liquid",
			"is_default": 0,
			"is_active": 1,
			"description": "PoC catalogue scheme — display only.",
		},
	]
	out = []
	for row in defaults:
		if frappe.db.exists("LYQD Scheme", row["isin"]):
			out.append(frappe.get_doc("LYQD Scheme", row["isin"]).as_dict())
			continue
		doc = frappe.get_doc({"doctype": "LYQD Scheme", **row})
		doc.insert()
		out.append(doc.as_dict())
	return out
