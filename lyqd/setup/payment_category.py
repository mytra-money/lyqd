"""LYQD Payment Category — defaults, seed, resolve labels ↔ Link names."""

from __future__ import annotations

import frappe

# Seeded once per LYQD Company (after_insert / migrate). Labels match the old Select options.
DEFAULT_PAYMENT_CATEGORIES: tuple[dict, ...] = (
	{"category_name": "Salary", "allow_outflow": 1, "allow_inflow": 0},
	{"category_name": "Import-LC", "allow_outflow": 1, "allow_inflow": 0},
	{"category_name": "Vendor", "allow_outflow": 1, "allow_inflow": 0},
	{"category_name": "Customer", "allow_outflow": 0, "allow_inflow": 1},
	{"category_name": "Tax", "allow_outflow": 1, "allow_inflow": 0},
	{"category_name": "Loan", "allow_outflow": 1, "allow_inflow": 0},
	{"category_name": "FD Maturity", "allow_outflow": 0, "allow_inflow": 1},
	{"category_name": "Loan Proceeds", "allow_outflow": 0, "allow_inflow": 1},
	{"category_name": "Other", "allow_outflow": 1, "allow_inflow": 1},
)


def category_docname(company: str, category_name: str) -> str:
	"""Autoname expression used by LYQD Payment Category."""
	return f"{company}-{category_name}"


def ensure_default_payment_categories(company: str) -> list[str]:
	"""Create missing default categories for a company. Returns names created/ensured."""
	if not company or not frappe.db.exists("DocType", "LYQD Payment Category"):
		return []
	if not frappe.db.exists("LYQD Company", company):
		return []

	ensured: list[str] = []
	for spec in DEFAULT_PAYMENT_CATEGORIES:
		name = category_docname(company, spec["category_name"])
		if frappe.db.exists("LYQD Payment Category", name):
			ensured.append(name)
			continue
		# Prefer match by label if an older row was renamed/autonamed differently
		existing = frappe.db.get_value(
			"LYQD Payment Category",
			{"company": company, "category_name": spec["category_name"]},
			"name",
		)
		if existing:
			ensured.append(existing)
			continue
		doc = frappe.get_doc(
			{
				"doctype": "LYQD Payment Category",
				"company": company,
				"category_name": spec["category_name"],
				"allow_outflow": spec["allow_outflow"],
				"allow_inflow": spec["allow_inflow"],
				"disabled": 0,
			}
		)
		doc.insert(ignore_permissions=True)
		ensured.append(doc.name)
	return ensured


def get_category_label(category: str | None) -> str:
	"""Human label for a Link name (or pass-through if already a label / missing)."""
	if not category:
		return "Other"
	if not frappe.db.exists("DocType", "LYQD Payment Category"):
		return category
	label = frappe.db.get_value("LYQD Payment Category", category, "category_name")
	return label or category


def labelize_category_fields(rows: list[dict] | None, field: str = "category") -> None:
	"""In-place: replace Link names with category_name for SPA / charts / explanations."""
	if not rows:
		return
	if not frappe.db.exists("DocType", "LYQD Payment Category"):
		return
	names = {r.get(field) for r in rows if r.get(field)}
	if not names:
		return
	labels = {
		d.name: d.category_name
		for d in frappe.get_all(
			"LYQD Payment Category",
			filters={"name": ("in", list(names))},
			fields=["name", "category_name"],
		)
	}
	for r in rows:
		cat = r.get(field)
		if cat and cat in labels:
			r[field] = labels[cat]
			r["category_id"] = cat


def resolve_payment_category(
	company: str,
	category: str | None,
	cash_effect: str | None = None,
	*,
	create_if_missing: bool = True,
) -> str:
	"""
	Resolve SPA/API category (label or Link name) to a Payment Category docname.

	Creates a custom category for the company when the label is new (both directions
	allowed) unless create_if_missing is False.
	"""
	company = (company or "").strip()
	raw = (category or "").strip() or "Other"
	if not company:
		frappe.throw(frappe._("Company is required to resolve payment category"))

	ensure_default_payment_categories(company)

	# Already a valid Link for this company
	if frappe.db.exists("LYQD Payment Category", raw):
		row_company = frappe.db.get_value("LYQD Payment Category", raw, "company")
		if row_company == company:
			return raw

	# Label match (case-insensitive)
	found = frappe.db.sql(
		"""
		select name from `tabLYQD Payment Category`
		where company = %s and lower(category_name) = %s
		limit 1
		""",
		(company, raw.lower()),
	)
	if found:
		return found[0][0]

	# Expected autoname
	expected = category_docname(company, raw)
	if frappe.db.exists("LYQD Payment Category", expected):
		return expected

	if not create_if_missing:
		frappe.throw(
			frappe._("Payment Category {0} not found for {1}").format(raw, company)
		)

	# Custom category — allow both directions unless cash_effect hints one side
	allow_out = 1
	allow_in = 1
	if cash_effect == "Outflow":
		allow_in = 0
	elif cash_effect in ("Inflow", "Setoff"):
		allow_out = 0

	doc = frappe.get_doc(
		{
			"doctype": "LYQD Payment Category",
			"company": company,
			"category_name": raw,
			"allow_outflow": allow_out,
			"allow_inflow": allow_in,
			"disabled": 0,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def list_payment_categories(
	company: str,
	cash_effect: str | None = None,
	*,
	include_disabled: bool = False,
) -> list[dict]:
	"""Categories for SPA pickers, optionally filtered by Outflow / Inflow / Setoff."""
	company = (company or "").strip()
	if not company:
		return []
	ensure_default_payment_categories(company)

	filters: dict = {"company": company}
	if not include_disabled:
		filters["disabled"] = 0

	effect = (cash_effect or "").strip()
	if effect == "Outflow":
		filters["allow_outflow"] = 1
	elif effect in ("Inflow", "Setoff"):
		filters["allow_inflow"] = 1

	rows = frappe.get_all(
		"LYQD Payment Category",
		filters=filters,
		fields=["name", "category_name", "allow_outflow", "allow_inflow", "disabled"],
		order_by="category_name asc",
	)
	return rows


def migrate_upcoming_payment_categories() -> int:
	"""
	After Select→Link: map leftover label values on payments to company Link names.
	Returns number of rows updated.
	"""
	if not frappe.db.exists("DocType", "LYQD Payment Category"):
		return 0
	if not frappe.db.exists("DocType", "LYQD Upcoming Payment"):
		return 0

	updated = 0
	companies = frappe.get_all("LYQD Company", pluck="name")
	for company in companies:
		ensure_default_payment_categories(company)

	# Distinct category values still looking like labels (no company prefix match)
	rows = frappe.db.sql(
		"""
		select name, company, category
		from `tabLYQD Upcoming Payment`
		where ifnull(category, '') != ''
		""",
		as_dict=True,
	)
	for row in rows:
		cat = (row.category or "").strip()
		if not cat:
			continue
		# Already a link for this company
		if frappe.db.exists("LYQD Payment Category", cat):
			owner = frappe.db.get_value("LYQD Payment Category", cat, "company")
			if owner == row.company:
				continue
		try:
			link = resolve_payment_category(
				row.company, cat, create_if_missing=True
			)
		except Exception:
			frappe.log_error(title="LYQD migrate payment category")
			continue
		if link != cat:
			frappe.db.set_value(
				"LYQD Upcoming Payment",
				row.name,
				"category",
				link,
				update_modified=False,
			)
			updated += 1
	return updated
