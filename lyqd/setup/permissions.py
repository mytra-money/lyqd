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
	"""LYQD Companies the current user may see.

	System Manager / Administrator: all active companies.
	Everyone else: only companies granted via User Permission on LYQD Company.
	"""
	if not frappe.db.exists("DocType", "LYQD Company"):
		return []

	roles = set(frappe.get_roles())
	if frappe.session.user == "Administrator" or "System Manager" in roles:
		return frappe.get_all(
			"LYQD Company", filters={"is_active": 1}, pluck="name", order_by="name asc"
		)

	companies = frappe.get_all(
		"User Permission",
		filters={"user": frappe.session.user, "allow": "LYQD Company"},
		pluck="for_value",
		order_by="for_value asc",
	)
	# Keep only companies that still exist and are active
	out = []
	for name in companies or []:
		if name and frappe.db.exists("LYQD Company", name):
			if frappe.db.get_value("LYQD Company", name, "is_active"):
				out.append(name)
	return out


def ensure_lyqd_company_user_permission(company: str, user: str | None = None) -> bool:
	"""
	Grant User Permission for LYQD Company when the user is not a System Manager.

	Returns True if a permission was created (or already existed).
	"""
	user = user or frappe.session.user
	if not user or user in ("Guest", "Administrator"):
		return False
	if "System Manager" in frappe.get_roles(user):
		return False
	company = (company or "").strip()
	if not company or not frappe.db.exists("LYQD Company", company):
		return False

	existing = frappe.db.exists(
		"User Permission",
		{"user": user, "allow": "LYQD Company", "for_value": company},
	)
	if existing:
		return True

	frappe.get_doc(
		{
			"doctype": "User Permission",
			"user": user,
			"allow": "LYQD Company",
			"for_value": company,
			"apply_to_all_doctypes": 1,
		}
	).insert(ignore_permissions=True)
	return True


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


def get_lyqd_company_list_query(user: str | None = None) -> str:
	"""Restrict LYQD Company list itself."""
	if not user:
		user = frappe.session.user
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return ""
	companies = get_user_companies()
	if not companies:
		return "1=0"
	escaped = ", ".join(frappe.db.escape(c) for c in companies)
	return f"`tabLYQD Company`.name in ({escaped})"


def get_lyqd_bank_account_query(user: str | None = None) -> str:
	return _company_query_for("LYQD Bank Account", user)


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
	# LYQD Company itself is keyed by name; child docs use company Link
	doctype = getattr(doc, "doctype", None) or (doc.get("doctype") if hasattr(doc, "get") else None)
	if doctype == "LYQD Company":
		name = getattr(doc, "name", None) or (doc.get("name") if hasattr(doc, "get") else None)
		return name in companies if name else False
	company = getattr(doc, "company", None) or (doc.get("company") if hasattr(doc, "get") else None)
	return company in companies if company else True
