"""LYQD recommendation integration settings (local vs remote ERPNext).

Stored on the Single DocType **LYQD Settings** (not a separate ERPNext Settings).
"""

from __future__ import annotations

from typing import Any

import frappe


SOURCE_THIS_SITE = "This Site"
SOURCE_OTHER_SITE = "Other Site"


def get_integration_settings() -> dict[str, Any]:
	if not frappe.db.exists("DocType", "LYQD Settings"):
		return {
			"enabled": False,
			"source": SOURCE_THIS_SITE,
			"remote_site_url": None,
			"remote_company": None,
			"remote_api_key": None,
			"has_remote_api_secret": False,
		}
	doc = frappe.get_single("LYQD Settings")
	enabled = bool(doc.get("erpnext_integration_enabled"))
	source = doc.get("erpnext_source") or SOURCE_THIS_SITE
	return {
		"enabled": enabled,
		"source": source,
		"remote_site_url": (doc.get("remote_site_url") or "").rstrip("/") or None,
		"remote_company": (doc.get("remote_company") or "").strip() or None,
		"remote_api_key": (doc.get("remote_api_key") or "").strip() or None,
		"has_remote_api_secret": bool(
			doc.get_password("remote_api_secret", raise_exception=False)
			if hasattr(doc, "get_password")
			else False
		),
	}


def is_erpnext_integration_enabled() -> bool:
	return bool(get_integration_settings().get("enabled"))


def is_remote_source() -> bool:
	s = get_integration_settings()
	return bool(s.get("enabled") and s.get("source") == SOURCE_OTHER_SITE)


def get_remote_credentials() -> dict[str, str]:
	"""Return url, api_key, api_secret, company for Other Site mode."""
	if not frappe.db.exists("DocType", "LYQD Settings"):
		frappe.throw(frappe._("LYQD Settings not found"))
	doc = frappe.get_single("LYQD Settings")
	if not doc.erpnext_integration_enabled or (doc.erpnext_source or "") != SOURCE_OTHER_SITE:
		frappe.throw(frappe._("Remote ERPNext source is not enabled"))
	secret = doc.get_password("remote_api_secret", raise_exception=False)
	if not doc.remote_site_url or not doc.remote_api_key or not secret:
		frappe.throw(frappe._("Remote site URL, API Key, and API Secret are required"))
	return {
		"url": doc.remote_site_url.strip().rstrip("/"),
		"api_key": doc.remote_api_key.strip(),
		"api_secret": secret,
		"company": (doc.remote_company or "").strip() or None,
	}


def settings_for_api() -> dict[str, Any]:
	"""Safe settings payload for the SPA (never includes API secret)."""
	s = get_integration_settings()
	return {
		"enabled": 1 if s["enabled"] else 0,
		"source": s["source"],
		"remote_site_url": s["remote_site_url"] or "",
		"remote_company": s["remote_company"] or "",
		"remote_api_key": s["remote_api_key"] or "",
		"has_remote_api_secret": 1 if s["has_remote_api_secret"] else 0,
	}
