"""Install / migrate hooks for LYQD."""

from __future__ import annotations

import click
import frappe


LYQD_ROLES = (
	{
		"role_name": "LYQD User",
		"desk_access": 1,
		"description": "Manage upcoming payments, view surplus, update cash snapshots",
	},
	{
		"role_name": "LYQD Manager",
		"desk_access": 1,
		"description": "Edit LYQD Company (policy, books) and draft proposals; full surplus workflow",
	},
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
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": role["role_name"],
				"desk_access": role["desk_access"],
				"description": role["description"],
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
