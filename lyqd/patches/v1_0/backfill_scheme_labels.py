"""Copy LYQD Scheme names/ISINs onto Instruction and Holding before Link fields become Data."""

from __future__ import annotations

import frappe


def execute():
	_backfill_instructions()
	_backfill_holdings()


def _backfill_instructions():
	if not frappe.db.exists("DocType", "LYQD Investment Instruction"):
		return
	if not frappe.db.has_column("LYQD Investment Instruction", "scheme"):
		return
	rows = frappe.get_all(
		"LYQD Investment Instruction",
		fields=["name", "scheme", "scheme_label", "scheme_isin"],
	)
	for row in rows:
		scheme = (row.scheme or "").strip()
		if not scheme:
			continue
		label = row.scheme_label
		isin = row.scheme_isin
		if frappe.db.exists("DocType", "LYQD Scheme") and frappe.db.exists("LYQD Scheme", scheme):
			sn, si = frappe.db.get_value("LYQD Scheme", scheme, ["scheme_name", "isin"]) or (None, None)
			label = label or sn or scheme
			isin = isin or si or scheme
		else:
			label = label or scheme
			isin = isin or scheme
		frappe.db.set_value(
			"LYQD Investment Instruction",
			row.name,
			{"scheme_label": label, "scheme_isin": isin},
			update_modified=False,
		)


def _backfill_holdings():
	if not frappe.db.exists("DocType", "LYQD Holding"):
		return
	if not frappe.db.has_column("LYQD Holding", "scheme"):
		return
	# scheme_label / scheme_isin may not exist yet (pre_model_sync) — only enrich when columns exist
	has_label = frappe.db.has_column("LYQD Holding", "scheme_label")
	has_isin = frappe.db.has_column("LYQD Holding", "scheme_isin")
	rows = frappe.get_all("LYQD Holding", fields=["name", "scheme"])
	for row in rows:
		scheme = (row.scheme or "").strip()
		if not scheme:
			continue
		label, isin = scheme, scheme
		if frappe.db.exists("DocType", "LYQD Scheme") and frappe.db.exists("LYQD Scheme", scheme):
			sn, si = frappe.db.get_value("LYQD Scheme", scheme, ["scheme_name", "isin"]) or (None, None)
			label = sn or scheme
			isin = si or scheme
		vals = {}
		if has_label:
			vals["scheme_label"] = label
		if has_isin:
			vals["scheme_isin"] = isin
		if vals:
			frappe.db.set_value("LYQD Holding", row.name, vals, update_modified=False)
