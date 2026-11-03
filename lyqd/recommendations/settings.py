"""LYQD books / recommendation settings — scoped to LYQD Company."""

from __future__ import annotations

from typing import Any

import frappe


SOURCE_THIS_SITE = "This Site"
SOURCE_OTHER_SITE = "Other Site"
SOURCE_MANUAL = "Manual"


def _company_doc(company: str | None):
	company = (company or "").strip()
	if not company or not frappe.db.exists("DocType", "LYQD Company"):
		return None
	if not frappe.db.exists("LYQD Company", company):
		return None
	return frappe.get_doc("LYQD Company", company)


def effective_books_source(doc) -> str:
	"""
	Resolve Manual / This Site / Other Site.

	Prefer CRM-style checks (erpnext_enabled + is_erpnext_in_the_current_site)
	when present so a disabled checkbox never leaves a stale Other Site source.
	"""
	if doc and getattr(doc, "meta", None) and doc.meta.has_field("erpnext_enabled"):
		if not int(doc.erpnext_enabled or 0):
			return SOURCE_MANUAL
		if int(doc.is_erpnext_in_the_current_site or 0):
			return SOURCE_THIS_SITE
		return SOURCE_OTHER_SITE
	return (getattr(doc, "books_source", None) or SOURCE_MANUAL) if doc else SOURCE_MANUAL


def get_integration_settings(company: str | None = None) -> dict[str, Any]:
	"""
	Books connector for one LYQD Company.

	``enabled`` is True when books_source is This Site or Other Site.
	"""
	empty = {
		"company": company,
		"enabled": False,
		"source": SOURCE_THIS_SITE,
		"books_source": SOURCE_MANUAL,
		"remote_site_url": None,
		"remote_company": None,
		"remote_api_key": None,
		"has_remote_api_secret": False,
		"investment_account_activated": False,
		"investment_account_requested_on": None,
	}
	doc = _company_doc(company)
	if not doc:
		return empty

	books_source = effective_books_source(doc)
	# Heal stale books_source if checks disagree (e.g. after adding erpnext_enabled)
	if (doc.books_source or SOURCE_MANUAL) != books_source:
		frappe.db.set_value(
			"LYQD Company",
			doc.name,
			{
				"books_source": books_source,
				"erpnext_enabled": 0 if books_source == SOURCE_MANUAL else 1,
				"is_erpnext_in_the_current_site": 1 if books_source == SOURCE_THIS_SITE else 0,
			},
			update_modified=False,
		)
		doc.books_source = books_source

	if books_source == SOURCE_MANUAL:
		source = SOURCE_THIS_SITE
		enabled = False
	elif books_source == SOURCE_OTHER_SITE:
		source = SOURCE_OTHER_SITE
		enabled = True
	else:
		source = SOURCE_THIS_SITE
		enabled = True

	return {
		"company": doc.name,
		"enabled": enabled,
		"source": source,
		"books_source": books_source,
		"remote_site_url": (doc.remote_site_url or "").rstrip("/") or None,
		"remote_company": (doc.books_company or "").strip() or None,
		"remote_api_key": (doc.remote_api_key or "").strip() or None,
		"has_remote_api_secret": bool(
			doc.get_password("remote_api_secret", raise_exception=False)
		),
		"investment_account_activated": bool(doc.investment_account_activated),
		"investment_account_requested_on": doc.investment_account_requested_on,
	}


def is_erpnext_integration_enabled(company: str | None = None) -> bool:
	return bool(get_integration_settings(company).get("enabled"))


def is_remote_source(company: str | None = None) -> bool:
	s = get_integration_settings(company)
	return bool(s.get("enabled") and s.get("source") == SOURCE_OTHER_SITE)


def get_remote_credentials(company: str | None = None) -> dict[str, str]:
	"""Return url, api_key, api_secret, company for Other Site mode on this LYQD Company."""
	doc = _company_doc(company)
	if not doc:
		frappe.throw(frappe._("LYQD Company is required for remote books"))
	if (doc.books_source or "") != SOURCE_OTHER_SITE:
		frappe.throw(frappe._("Remote ERPNext source is not enabled for {0}").format(doc.name))
	secret = doc.get_password("remote_api_secret", raise_exception=False)
	if not doc.remote_site_url or not doc.remote_api_key or not secret:
		frappe.throw(frappe._("Remote site URL, API Key, and API Secret are required"))
	return {
		"url": doc.remote_site_url.strip().rstrip("/"),
		"api_key": doc.remote_api_key.strip(),
		"api_secret": secret,
		"company": (doc.books_company or "").strip() or None,
		"lyqd_company": doc.name,
	}


def settings_for_api(company: str | None = None) -> dict[str, Any]:
	"""Safe settings payload for the SPA (never includes API secret)."""
	s = get_integration_settings(company)
	return {
		"company": s.get("company") or company or "",
		"enabled": 1 if s["enabled"] else 0,
		"source": s["source"],
		"books_source": s.get("books_source") or SOURCE_MANUAL,
		"remote_site_url": s["remote_site_url"] or "",
		"remote_company": s["remote_company"] or "",
		"remote_api_key": s["remote_api_key"] or "",
		"has_remote_api_secret": 1 if s["has_remote_api_secret"] else 0,
		"investment_account_activated": 1 if s.get("investment_account_activated") else 0,
		"investment_account_requested_on": s.get("investment_account_requested_on") or "",
	}
