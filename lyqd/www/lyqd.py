# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

from __future__ import annotations

import json
import re
from urllib.parse import urlencode

import frappe
import frappe.sessions
from frappe import _
from frappe.utils.jinja_globals import is_rtl
from frappe.utils.user import is_website_user

no_cache = 1

SCRIPT_TAG_PATTERN = re.compile(r"<script[^<]*</script>")
CLOSING_SCRIPT_TAG_PATTERN = re.compile(r"</script>")


def get_context(context):
	validate_lyqd_user()
	csrf_token = frappe.sessions.get_csrf_token()
	frappe.db.commit()  # nosemgrep — persist CSRF like CRM/banking

	context = frappe._dict()
	context.boot = get_boot()
	context.boot.csrf_token = csrf_token
	context.csrf_token = csrf_token
	context.build_version = frappe.utils.get_build_version()
	context.app_name = "LYQD by Mytra"
	context.layout_direction = "rtl" if is_rtl() else "ltr"
	context.lang = frappe.local.lang
	return context


def validate_lyqd_user():
	if frappe.session.user == "Guest":
		frappe.response["status_code"] = 403
		frappe.msgprint(_("Log in to access LYQD."))
		frappe.redirect(f"/login?{urlencode({'redirect-to': frappe.request.path})}")

	elif is_website_user():
		frappe.throw(_("You are not permitted to access LYQD."), frappe.PermissionError)

	roles = set(frappe.get_roles())
	if not roles.intersection({"System Manager", "LYQD Manager", "LYQD User", "Administrator"}):
		# Administrator role string may not appear in get_roles for Administrator user
		if frappe.session.user != "Administrator":
			frappe.throw(_("LYQD User or LYQD Manager role required."), frappe.PermissionError)


@frappe.whitelist(methods=["POST"], allow_guest=True)
def get_context_for_dev():
	if not frappe.conf.developer_mode:
		frappe.throw(_("This method is only meant for developer mode"))
	validate_lyqd_user()
	boot = get_boot()
	boot["csrf_token"] = frappe.sessions.get_csrf_token()
	return boot


def get_boot():
	from lyqd.setup.permissions import get_user_companies

	return frappe._dict(
		{
			"frappe_version": frappe.__version__,
			"sitename": frappe.local.site,
			"user": frappe.session.user,
			"user_fullname": frappe.utils.get_fullname(frappe.session.user)
			if frappe.session.user != "Guest"
			else "",
			"user_image": (
				frappe.db.get_value("User", frappe.session.user, "user_image")
				if frappe.session.user != "Guest"
				else None
			),
			"default_route": "/lyqd",
			"companies": get_user_companies()
			or frappe.get_all("Company", pluck="name", order_by="name asc"),
			"default_company": frappe.defaults.get_user_default("Company"),
			"roles": frappe.get_roles(),
			"developer_mode": bool(frappe.conf.developer_mode),
			"tagline": "Make idle cash work smarter.",
			"app_name": "LYQD by Mytra",
			"erpnext_integration_enabled": bool(
				frappe.db.exists("DocType", "LYQD ERPNext Settings")
				and frappe.db.get_single_value("LYQD ERPNext Settings", "enabled")
			),
		}
	)
