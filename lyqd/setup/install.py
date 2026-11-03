"""Install / migrate hooks for LYQD."""

from __future__ import annotations

import click
import frappe
from frappe.utils import cint


# SPA-only roles — no Desk. Users work in /lyqd (Website User is fine).
LYQD_ROLES = (
	{"role_name": "LYQD User", "desk_access": 0},
	{"role_name": "LYQD Manager", "desk_access": 0},
)


def after_install() -> None:
	create_roles()
	ensure_settings()
	ensure_custom_fields()
	click.secho("LYQD by Mytra installed. Open the LYQD workspace to start.", fg="green")


def after_migrate() -> None:
	create_roles()
	ensure_settings()
	ensure_custom_fields()


def ensure_custom_fields() -> None:
	try:
		from lyqd.cash.mirror_banks import ensure_bank_account_custom_fields

		ensure_bank_account_custom_fields()
	except Exception:
		frappe.log_error(title="LYQD ensure bank account custom fields")


def create_roles() -> None:
	for role in LYQD_ROLES:
		if frappe.db.exists("Role", role["role_name"]):
			doc = frappe.get_doc("Role", role["role_name"])
			if cint(doc.desk_access) != cint(role["desk_access"]):
				doc.desk_access = role["desk_access"]
				doc.flags.ignore_permissions = True
				doc.save()
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": role["role_name"],
				"desk_access": role["desk_access"],
			}
		)
		doc.insert(ignore_permissions=True)


def ensure_settings() -> None:
	if not frappe.db.exists("LYQD Settings", "LYQD Settings"):
		# Single doctypes are created on first get_single / migrate sync
		return
	settings = frappe.get_single("LYQD Settings")
	dirty = False
	if not settings.display_scheme_label:
		settings.display_scheme_label = "ICICI Prudential Liquid Fund"
		dirty = True
	if not settings.display_scheme_isin:
		settings.display_scheme_isin = "INF109K01VQ1"
		dirty = True
	if not settings.default_forecast_horizon_days:
		settings.default_forecast_horizon_days = 7
		dirty = True
	if dirty:
		settings.flags.ignore_permissions = True
		settings.save()
