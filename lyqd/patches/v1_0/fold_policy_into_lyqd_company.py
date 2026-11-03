"""Copy LYQD Policy scalars + child rows onto LYQD Company, then delete Policy."""

from __future__ import annotations

import frappe
from frappe.utils import flt


def execute():
	if not frappe.db.exists("DocType", "LYQD Company"):
		return
	if not frappe.db.exists("DocType", "LYQD Policy"):
		return

	# Ensure new columns exist (post_model_sync should have synced Company first)
	for field in (
		"min_liquidity_buffer",
		"restricted_cash",
		"default_forecast_horizon_days",
		"enable_purchase_invoice_recommendations",
	):
		if not frappe.db.has_column("LYQD Company", field):
			return

	policies = frappe.get_all(
		"LYQD Policy",
		fields=[
			"name",
			"company",
			"min_liquidity_buffer",
			"restricted_cash",
			"default_forecast_horizon_days",
			"notes",
			"enable_purchase_invoice_recommendations",
		],
	)

	for pol in policies:
		company = pol.company
		if not company or not frappe.db.exists("LYQD Company", company):
			continue

		co = frappe.get_doc("LYQD Company", company)
		co.min_liquidity_buffer = flt(pol.min_liquidity_buffer)
		co.restricted_cash = flt(pol.restricted_cash)
		co.default_forecast_horizon_days = int(pol.default_forecast_horizon_days or 7)
		if pol.enable_purchase_invoice_recommendations is not None:
			co.enable_purchase_invoice_recommendations = int(
				pol.enable_purchase_invoice_recommendations
			)
		if pol.notes and not co.notes:
			co.notes = pol.notes

		co.set("eligible_bank_accounts", [])
		for row in frappe.get_all(
			"LYQD Policy Bank Account",
			filters={"parent": pol.name},
			fields=["bank_account", "account_name", "gl_account"],
			order_by="idx asc",
		):
			if not row.bank_account:
				continue
			co.append(
				"eligible_bank_accounts",
				{
					"bank_account": row.bank_account,
					"account_name": row.account_name,
					"gl_account": row.gl_account,
				},
			)

		co.set("recommendation_accounts", [])
		for row in frappe.get_all(
			"LYQD Recommendation Account",
			filters={"parent": pol.name},
			fields=["account", "account_name", "show_references"],
			order_by="idx asc",
		):
			if not row.account:
				continue
			co.append(
				"recommendation_accounts",
				{
					"account": row.account,
					"account_name": row.account_name,
					"show_references": row.show_references,
				},
			)

		co.flags.ignore_validate = True
		co.save(ignore_permissions=True)

		# Point Surplus Run.policy at the company
		if frappe.db.exists("DocType", "LYQD Surplus Run") and frappe.db.has_column(
			"LYQD Surplus Run", "policy"
		):
			frappe.db.sql(
				"""
				update `tabLYQD Surplus Run`
				set policy = %s
				where policy = %s
				""",
				(company, pol.name),
			)

	# DocType Python module may already be removed from the app — use SQL
	frappe.db.sql("delete from `tabLYQD Policy Bank Account` where parenttype = 'LYQD Policy'")
	frappe.db.sql(
		"delete from `tabLYQD Recommendation Account` where parenttype = 'LYQD Policy'"
	)
	if frappe.db.table_exists("LYQD Policy"):
		frappe.db.sql("delete from `tabLYQD Policy`")
		frappe.db.sql_ddl("drop table if exists `tabLYQD Policy`")

	if frappe.db.exists("DocType", "LYQD Policy"):
		# Remove meta without loading the controller module
		frappe.db.delete("DocType", {"name": "LYQD Policy"})
		frappe.db.delete("DocField", {"parent": "LYQD Policy"})
		frappe.db.delete("DocPerm", {"parent": "LYQD Policy"})
		frappe.db.delete("Custom Field", {"dt": "LYQD Policy"})
		frappe.db.delete("Property Setter", {"doc_type": "LYQD Policy"})
		frappe.db.delete("Custom DocPerm", {"parent": "LYQD Policy"})

	frappe.clear_cache(doctype="LYQD Policy")
