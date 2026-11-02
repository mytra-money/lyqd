"""Role helpers and company-scoped permissions for LYQD DocTypes."""

from __future__ import annotations

import frappe


def has_app_permission() -> bool:
	"""Show LYQD on the Apps screen for LYQD roles / System Manager."""
	user = frappe.session.user
	if user == "Administrator":
		return True
	roles = set(frappe.get_roles(user))
	return bool(roles.intersection({"System Manager", "LYQD Manager", "LYQD User"}))


def get_user_companies() -> list[str]:
	"""Companies the current user may see (User Permission + defaults)."""
	if "System Manager" in frappe.get_roles():
		return [c.name for c in frappe.get_all("Company")]

	companies = frappe.get_all(
		"User Permission",
		filters={"user": frappe.session.user, "allow": "Company"},
		pluck="for_value",
	)
	if companies:
		return companies

	default = frappe.defaults.get_user_default("Company")
	return [default] if default else []


def _company_query_for(doctype: str, user: str | None = None) -> str:
	if not user:
		user = frappe.session.user
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return ""

	companies = get_user_companies()
	if not companies:
		return "1=0"

	escaped = ", ".join(frappe.db.escape(c) for c in companies)
	return f"`tab{doctype}`.company in ({escaped})"


def get_lyqd_policy_query(user: str | None = None) -> str:
	return _company_query_for("LYQD Policy", user)


def get_lyqd_upcoming_payment_query(user: str | None = None) -> str:
	return _company_query_for("LYQD Upcoming Payment", user)


def get_lyqd_surplus_run_query(user: str | None = None) -> str:
	return _company_query_for("LYQD Surplus Run", user)


def get_lyqd_cash_snapshot_query(user: str | None = None) -> str:
	return _company_query_for("LYQD Cash Snapshot", user)


def get_lyqd_draft_proposal_query(user: str | None = None) -> str:
	return _company_query_for("LYQD Draft Proposal", user)


def get_lyqd_instruction_query(user: str | None = None) -> str:
	return _company_query_for("LYQD Investment Instruction", user)


def get_lyqd_holding_query(user: str | None = None) -> str:
	return _company_query_for("LYQD Holding", user)


def has_company_permission(doc, user: str | None = None, permission_type: str | None = None) -> bool:
	if not user:
		user = frappe.session.user
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return True
	companies = get_user_companies()
	if not companies:
		return False
	company = getattr(doc, "company", None) or (doc.get("company") if hasattr(doc, "get") else None)
	return company in companies if company else True
