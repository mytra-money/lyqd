"""Fetch liability recommendations from a remote ERPNext site (API Key + Secret).

Uses stock Frappe REST only — no custom app required on the remote site.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import flt, getdate, today

from lyqd.recommendations.settings import get_remote_credentials


def _client_from_cred(url: str, api_key: str, api_secret: str):
	from frappe.frappeclient import FrappeClient

	return FrappeClient(
		(url or "").strip().rstrip("/"),
		api_key=(api_key or "").strip(),
		api_secret=api_secret,
		verify=True,
	)


def get_remote_client(lyqd_company: str | None = None):
	"""Return (FrappeClient, remote books company name) for a LYQD Company."""
	cred = get_remote_credentials(lyqd_company)
	client = _client_from_cred(cred["url"], cred["api_key"], cred["api_secret"])
	company = cred.get("company") or resolve_remote_company(client)
	# Persist resolved books company on the LYQD Company when blank
	lyqd_name = cred.get("lyqd_company") or lyqd_company
	if (
		company
		and lyqd_name
		and frappe.db.exists("LYQD Company", lyqd_name)
		and not (frappe.db.get_value("LYQD Company", lyqd_name, "books_company") or "").strip()
	):
		frappe.db.set_value("LYQD Company", lyqd_name, "books_company", company, update_modified=False)
	return client, company


def list_remote_companies(client) -> list[str]:
	rows = client.get_list("Company", fields=["name"], order_by="name asc", limit_page_length=100) or []
	return [r["name"] for r in rows if r.get("name")]


def resolve_remote_company(client, preferred: str | None = None) -> str:
	"""Resolve a remote Company. Preferred name is required when the site has multiple companies."""
	preferred = (preferred or "").strip() or None
	companies = list_remote_companies(client)
	if not companies:
		frappe.throw(frappe._("No Company found on the remote ERPNext site."))
	if preferred:
		if preferred not in companies:
			frappe.throw(
				frappe._(
					"Company {0} was not found on the remote site. Choose one of: {1}"
				).format(preferred, ", ".join(companies[:12]))
			)
		return preferred
	if len(companies) == 1:
		return companies[0]
	frappe.throw(
		frappe._(
			"Remote company is required. This site has {0} companies — select which books company LYQD should use."
		).format(len(companies))
	)


def probe_remote_connection(
	url: str,
	api_key: str,
	api_secret: str,
	company: str | None = None,
) -> dict[str, Any]:
	"""
	Validate draft credentials and return remote companies.

	When ``company`` is set, validates it exists on the remote site.
	When omitted and multiple companies exist, returns the list without picking one.
	"""
	url = (url or "").strip().rstrip("/")
	api_key = (api_key or "").strip()
	if not url or not api_key or not api_secret:
		frappe.throw(frappe._("Site URL, API Key, and API Secret are required."))
	if not url.startswith("http://") and not url.startswith("https://"):
		frappe.throw(frappe._("Site URL must start with http:// or https://"))

	client = _client_from_cred(url, api_key, api_secret)
	companies = list_remote_companies(client)
	if not companies:
		frappe.throw(frappe._("Connected, but no Company was found on that site."))

	preferred = (company or "").strip()
	if preferred:
		if preferred not in companies:
			frappe.throw(
				frappe._(
					"Company {0} was not found on the remote site. Choose one of: {1}"
				).format(preferred, ", ".join(companies[:12]))
			)
		resolved = preferred
	elif len(companies) == 1:
		resolved = companies[0]
	else:
		return {
			"ok": True,
			"company": None,
			"companies": companies,
			"message": frappe._(
				"Connected. Select the remote company LYQD should use ({0} found)."
			).format(len(companies)),
		}

	# Confirm books access for the resolved company
	client.get_list("Account", filters={"company": resolved}, fields=["name"], limit_page_length=1)
	return {
		"ok": True,
		"company": resolved,
		"companies": companies,
		"message": frappe._("Connected. Using company {0} on the remote site.").format(resolved),
	}


def list_remote_recommendation_accounts(
	root_types: list[str] | None = None,
	account_type: str | None = None,
	search: str | None = None,
	limit: int = 500,
	lyqd_company: str | None = None,
) -> list[dict[str, Any]]:
	"""Leaf accounts from the configured remote ERPNext (for Integrations picker)."""
	client, company = get_remote_client(lyqd_company)
	root_types = root_types or ["Liability", "Asset"]
	filters: dict[str, Any] = {
		"company": company,
		"is_group": 0,
		"root_type": ["in", root_types],
	}
	if account_type and account_type != "All":
		filters["account_type"] = account_type

	rows = (
		client.get_list(
			"Account",
			filters=filters,
			fields=["name", "account_name", "account_type", "root_type"],
			order_by="root_type asc, account_name asc",
			limit_page_length=min(int(limit or 500), 500),
		)
		or []
	)
	q = (search or "").strip().lower()
	if q:
		rows = [
			r
			for r in rows
			if q in (r.get("name") or "").lower()
			or q in (r.get("account_name") or "").lower()
			or q in (r.get("account_type") or "").lower()
		]
	for r in rows:
		r["source"] = "Other Site"
		r["books_company"] = company
	return rows


def _classify_accounts(client, account_names: list[str]) -> tuple[list[str], list[str], list[str]]:
	if not account_names:
		return [], [], []
	meta = client.get_list(
		"Account",
		filters={"name": ["in", account_names]},
		fields=["name", "account_type", "root_type", "account_name"],
		limit_page_length=len(account_names) + 5,
	) or []
	payable, receivable, other = [], [], []
	for a in meta:
		atype = a.get("account_type")
		if atype == "Payable":
			payable.append(a["name"])
		elif atype == "Receivable":
			receivable.append(a["name"])
		else:
			other.append(a["name"])
	# Keep unconfigured names as other so user selection still tries GL
	known = {a["name"] for a in meta}
	for name in account_names:
		if name not in known:
			other.append(name)
	return payable, receivable, other


def _remote_party_labels(client, party_type: str, parties: list[str]) -> dict[str, str]:
	"""Map Customer/Supplier name → display label from remote site."""
	parties = [p for p in parties if p]
	if not parties or not party_type:
		return {}
	doctype = party_type
	name_field = {
		"Customer": "customer_name",
		"Supplier": "supplier_name",
		"Employee": "employee_name",
	}.get(party_type)
	if not name_field:
		return {p: p for p in parties}
	out: dict[str, str] = {}
	for i in range(0, len(parties), 50):
		chunk = parties[i : i + 50]
		try:
			rows = (
				client.get_list(
					doctype,
					filters={"name": ["in", chunk]},
					fields=["name", name_field],
					limit_page_length=len(chunk) + 5,
				)
				or []
			)
			for r in rows:
				out[r["name"]] = r.get(name_field) or r["name"]
		except Exception:
			for p in chunk:
				out.setdefault(p, p)
	for p in parties:
		out.setdefault(p, p)
	return out


def _account_meta_map(client, account_names: list[str]) -> dict[str, dict]:
	if not account_names:
		return {}
	rows = (
		client.get_list(
			"Account",
			filters={"name": ["in", account_names]},
			fields=["name", "account_name", "account_type", "root_type"],
			limit_page_length=len(account_names) + 5,
		)
		or []
	)
	return {r["name"]: r for r in rows}


def _pi_voucher_rows(
	client,
	company: str,
	payable_accounts: list[str],
	as_of: str,
) -> list[dict[str, Any]]:
	"""Open Purchase Invoices (stock fields) — no custom remote method."""
	if not payable_accounts:
		return []
	filters: dict[str, Any] = {
		"company": company,
		"docstatus": 1,
		"outstanding_amount": [">", 0.01],
		"posting_date": ["<=", as_of],
		"credit_to": ["in", payable_accounts],
	}
	rows = (
		client.get_list(
			"Purchase Invoice",
			filters=filters,
			fields=[
				"name",
				"supplier",
				"supplier_name",
				"outstanding_amount",
				"due_date",
				"credit_to",
				"bill_no",
				"currency",
				"party_account_currency",
				"conversion_rate",
				"posting_date",
			],
			order_by="due_date asc",
			limit_page_length=100,
		)
		or []
	)
	from lyqd.fx import invoice_outstanding_in_company_currency

	company_ccy = _remote_company_currency(client, company)
	out = []
	for row in rows:
		amount = invoice_outstanding_in_company_currency(row, company_ccy, as_of=as_of)
		if amount <= 0.01:
			continue
		party_label = row.get("supplier_name") or row.get("supplier")
		title = f"Purchase Invoice {row['name']}"
		if party_label:
			title = f"{party_label} · {title}"
		out.append(
			{
				"grain": "voucher",
				"account": row.get("credit_to"),
				"source_doctype": "Purchase Invoice",
				"source_name": row["name"],
				"title": title[:140],
				"category": "Vendor",
				"due_date": str(row["due_date"]) if row.get("due_date") else None,
				"amount": amount,
				"cash_effect": "Outflow",
				"party_type": "Supplier",
				"party": row.get("supplier"),
				"party_name": party_label,
				"engine": "remote_purchase_invoice",
			}
		)
	return out


def _si_voucher_rows(
	client,
	company: str,
	receivable_accounts: list[str],
	as_of: str,
) -> list[dict[str, Any]]:
	"""Open Sales Invoices on receivable accounts — outstanding already nets PE/JE allocations."""
	if not receivable_accounts:
		return []
	filters: dict[str, Any] = {
		"company": company,
		"docstatus": 1,
		"outstanding_amount": [">", 0.01],
		"posting_date": ["<=", as_of],
		"debit_to": ["in", receivable_accounts],
	}
	rows = (
		client.get_list(
			"Sales Invoice",
			filters=filters,
			fields=[
				"name",
				"customer",
				"customer_name",
				"outstanding_amount",
				"due_date",
				"debit_to",
				"currency",
				"party_account_currency",
				"conversion_rate",
				"posting_date",
			],
			order_by="due_date asc",
			limit_page_length=100,
		)
		or []
	)
	from lyqd.fx import invoice_outstanding_in_company_currency

	company_ccy = _remote_company_currency(client, company)
	out = []
	for row in rows:
		amount = invoice_outstanding_in_company_currency(row, company_ccy, as_of=as_of)
		if amount <= 0.01:
			continue
		party_label = row.get("customer_name") or row.get("customer")
		title = f"Sales Invoice {row['name']}"
		if party_label:
			title = f"{party_label} · {title}"
		out.append(
			{
				"grain": "voucher",
				"account": row.get("debit_to"),
				"source_doctype": "Sales Invoice",
				"source_name": row["name"],
				"title": title[:140],
				"category": "Customer",
				"due_date": str(row["due_date"]) if row.get("due_date") else None,
				"amount": amount,
				"cash_effect": "Setoff",
				"party_type": "Customer",
				"party": row.get("customer"),
				"party_name": party_label,
				"engine": "remote_sales_invoice",
			}
		)
	return out


def _sum_gl_for_account(
	client, company: str, account: str, as_of: str, *, as_asset: bool = False
) -> float:
	"""Net GL from remote for one account (sync / single-row refresh)."""
	totals = _sum_gl_for_accounts(client, company, [account], as_of)
	signed = totals.get(account) or 0.0
	# _sum_gl_for_accounts stores liability-style (credit−debit); flip for assets
	if as_asset:
		return flt(-signed)
	return flt(signed)


def _sum_gl_for_accounts(
	client, company: str, accounts: list[str], as_of: str
) -> dict[str, float]:
	"""Net GL (credit−debit) per account in **one** paginated remote GL scan.

	Avoids N HTTP round-trips (one per account) which dominate Other Site latency
	and explode on large ledgers.
	"""
	accounts = [a for a in accounts if a]
	if not accounts:
		return {}
	totals: dict[str, float] = {a: 0.0 for a in accounts}
	start = 0
	page = 500
	# Hard cap pages so a huge remote ledger cannot hang the SPA forever
	max_start = 20_000
	while start <= max_start:
		rows = (
			client.get_list(
				"GL Entry",
				filters={
					"company": company,
					"account": ["in", accounts],
					"is_cancelled": 0,
					"posting_date": ["<=", as_of],
				},
				fields=["account", "debit", "credit"],
				limit_start=start,
				limit_page_length=page,
			)
			or []
		)
		if not rows:
			break
		for r in rows:
			acc = r.get("account")
			if acc not in totals:
				continue
			# liability-style signed net
			totals[acc] = flt(totals[acc]) + flt(r.get("credit")) - flt(r.get("debit"))
		if len(rows) < page:
			break
		start += page
	return totals


def _gl_voucher_rows(
	client,
	company: str,
	accounts: list[str],
	as_of: str,
	meta: dict[str, dict],
) -> list[dict[str, Any]]:
	"""Open GL by against_voucher so PE/JE settlements net against the invoice."""
	if not accounts:
		return []
	# Pull GL lines and aggregate in LYQD by against_voucher (+ party), not voucher_no
	start = 0
	page = 200
	buckets: dict[tuple, float] = {}
	while True:
		rows = (
			client.get_list(
				"GL Entry",
				filters={
					"company": company,
					"account": ["in", accounts],
					"is_cancelled": 0,
					"posting_date": ["<=", as_of],
				},
				fields=[
					"account",
					"voucher_type",
					"voucher_no",
					"against_voucher_type",
					"against_voucher",
					"party_type",
					"party",
					"debit",
					"credit",
				],
				limit_start=start,
				limit_page_length=page,
			)
			or []
		)
		if not rows:
			break
		for r in rows:
			src_dt = r.get("against_voucher_type") or r.get("voucher_type")
			src_dn = r.get("against_voucher") or r.get("voucher_no")
			if not src_dt or not src_dn:
				continue
			key = (r.get("account"), src_dt, src_dn, r.get("party_type"), r.get("party"))
			buckets[key] = buckets.get(key, 0.0) + flt(r.get("credit")) - flt(r.get("debit"))
		if len(rows) < page:
			break
		start += page
		if start > 8000:
			break

	# Resolve customer/supplier display names in bulk
	by_party_type: dict[str, set[str]] = {}
	for _account, _src_dt, _src_dn, party_type, party in buckets:
		if party_type and party:
			by_party_type.setdefault(party_type, set()).add(party)
	party_labels: dict[tuple[str, str], str] = {}
	for ptype, parties in by_party_type.items():
		for name, label in _remote_party_labels(client, ptype, list(parties)).items():
			party_labels[(ptype, name)] = label

	out = []
	for key, raw_amt in buckets.items():
		account, src_dt, src_dn, party_type, party = key
		root = (meta.get(account) or {}).get("root_type") or "Liability"
		if root == "Asset":
			amount = -flt(raw_amt)
			cash_effect = "Setoff"
		else:
			amount = flt(raw_amt)
			cash_effect = "Outflow"
		if amount <= 0.01:
			continue
		acc_name = (meta.get(account) or {}).get("account_name") or account
		party_label = party_labels.get((party_type or "", party or "")) or party
		if party_label:
			title = f"{party_label} · {src_dt} {src_dn}"
		else:
			title = f"{acc_name} · {src_dt} {src_dn}"
		if src_dt == "Sales Invoice" or party_type == "Customer":
			category = "Customer"
		elif src_dt == "Purchase Receipt" or party_type == "Supplier":
			category = "Vendor"
		else:
			category = "Tax"
		out.append(
			{
				"grain": "voucher",
				"account": account,
				"source_doctype": src_dt,
				"source_name": src_dn,
				"title": title[:140],
				"category": category,
				"due_date": None,
				"amount": amount,
				"cash_effect": cash_effect,
				"party_type": party_type,
				"party": party,
				"party_name": party_label,
				"engine": "remote_gl",
			}
		)
	return _exclude_billed_purchase_receipts_remote(client, out)


def _account_balance_rows(
	client,
	company: str,
	accounts: list[str],
	as_of: str,
	meta: dict[str, dict],
) -> list[dict[str, Any]]:
	from lyqd.recommendations.core import interpret_account_gl_balance

	if not accounts:
		return []
	# Bulk GL pull — liability-style nets; flip sign for Asset accounts below
	liability_nets = _sum_gl_for_accounts(client, company, accounts, as_of)
	out = []
	for account in accounts:
		root = (meta.get(account) or {}).get("root_type")
		acc_name = (meta.get(account) or {}).get("account_name") or account
		liab_signed = flt(liability_nets.get(account))
		signed = flt(-liab_signed) if root == "Asset" else liab_signed
		category = "Tax" if root in ("Asset", "Liability") else "Other"
		interp = interpret_account_gl_balance(root, signed, acc_name)
		if interp["cleared"] or flt(interp["amount"]) <= 0.01:
			continue
		out.append(
			{
				"grain": "account",
				"account": account,
				"source_doctype": "Account",
				"source_name": account,
				"title": interp["title"][:140],
				"category": category,
				"due_date": None,
				"amount": interp["amount"],
				"cash_effect": interp["cash_effect"],
				"party_type": None,
				"party": None,
				"engine": "remote_gl_balance",
			}
		)
	return out


def fetch_remote_recommendation_items(
	account_rows: list[dict[str, Any]],
	as_of: str | None = None,
	lyqd_company: str | None = None,
) -> list[dict[str, Any]]:
	"""Build recommendation items from remote site for configured accounts."""
	client, company = get_remote_client(lyqd_company)
	as_of = str(getdate(as_of or today()))
	all_accounts = [r.get("account") for r in account_rows if r.get("account")]
	meta = _account_meta_map(client, all_accounts)

	ref_accounts = [r["account"] for r in account_rows if r.get("show_references")]
	bal_accounts = [r["account"] for r in account_rows if not r.get("show_references")]

	payable_ref, receivable_ref, other_ref = _classify_accounts(client, ref_accounts)

	items: list[dict[str, Any]] = []
	items.extend(_pi_voucher_rows(client, company, payable_ref, as_of))
	items.extend(_si_voucher_rows(client, company, receivable_ref, as_of))
	items.extend(_gl_voucher_rows(client, company, other_ref, as_of, meta))
	items.extend(_account_balance_rows(client, company, bal_accounts, as_of, meta))
	return _exclude_billed_purchase_receipts_remote(client, items)


def remote_purchase_receipts_with_invoice(client, names: list[str]) -> set[str]:
	"""Remote PRs that already have a Purchase Invoice (per_billed or PI Item link)."""
	names = [n for n in names if n]
	if not names:
		return set()
	billed: set[str] = set()
	# Chunk to stay within API filter limits
	for i in range(0, len(names), 50):
		chunk = names[i : i + 50]
		try:
			rows = (
				client.get_list(
					"Purchase Receipt",
					filters={"name": ["in", chunk], "per_billed": [">", 0]},
					fields=["name"],
					limit_page_length=len(chunk) + 5,
				)
				or []
			)
			billed.update(r["name"] for r in rows if r.get("name"))
		except Exception:
			# Fallback: check each PR's per_billed
			for name in chunk:
				try:
					one = client.get_list(
						"Purchase Receipt",
						filters={"name": name},
						fields=["name", "per_billed"],
						limit_page_length=1,
					) or []
					if one and flt(one[0].get("per_billed")) > 0:
						billed.add(name)
				except Exception:
					pass
		try:
			pi_rows = (
				client.get_list(
					"Purchase Invoice Item",
					filters={"purchase_receipt": ["in", chunk], "docstatus": 1},
					fields=["purchase_receipt"],
					limit_page_length=500,
				)
				or []
			)
			billed.update(r["purchase_receipt"] for r in pi_rows if r.get("purchase_receipt"))
		except Exception:
			pass
	return billed


def _exclude_billed_purchase_receipts_remote(client, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
	pr_names = [
		i.get("source_name")
		for i in items
		if i.get("source_doctype") == "Purchase Receipt" and i.get("source_name")
	]
	if not pr_names:
		return items
	billed = remote_purchase_receipts_with_invoice(client, pr_names)
	if not billed:
		return items
	return [
		i
		for i in items
		if not (
			i.get("source_doctype") == "Purchase Receipt" and i.get("source_name") in billed
		)
	]


def remote_purchase_invoice_outstanding(name: str, lyqd_company: str | None = None) -> dict[str, Any]:
	return _remote_invoice_outstanding("Purchase Invoice", name, lyqd_company=lyqd_company)


def remote_sales_invoice_outstanding(name: str, lyqd_company: str | None = None) -> dict[str, Any]:
	return _remote_invoice_outstanding("Sales Invoice", name, lyqd_company=lyqd_company)


def _remote_company_currency(client, books_company: str, lyqd_company: str | None = None) -> str:
	from lyqd.fx import get_lyqd_company_currency

	company_ccy = get_lyqd_company_currency(lyqd_company)
	try:
		co_rows = (
			client.get_list(
				"Company",
				filters={"name": books_company},
				fields=["default_currency"],
				limit_page_length=1,
			)
			or []
		)
		if co_rows and co_rows[0].get("default_currency"):
			return str(co_rows[0]["default_currency"]).upper()
	except Exception:
		pass
	return company_ccy


def _remote_invoice_outstanding(
	doctype: str, name: str, lyqd_company: str | None = None
) -> dict[str, Any]:
	from lyqd.fx import invoice_outstanding_in_company_currency

	client, books_company = get_remote_client(lyqd_company)
	rows = client.get_list(
		doctype,
		filters={"name": name},
		fields=[
			"name",
			"outstanding_amount",
			"docstatus",
			"due_date",
			"status",
			"currency",
			"party_account_currency",
			"conversion_rate",
			"posting_date",
		],
		limit_page_length=1,
	)
	if not rows:
		return {"ok": True, "grain": "voucher", "amount": 0.0, "cleared": True, "missing": True}
	inv = rows[0]
	if int(inv.get("docstatus") or 0) == 2:
		return {
			"ok": True,
			"grain": "voucher",
			"amount": 0.0,
			"cleared": True,
			"cancelled": True,
			"due_date": inv.get("due_date"),
		}
	company_ccy = _remote_company_currency(client, books_company, lyqd_company)
	amt = invoice_outstanding_in_company_currency(inv, company_ccy)
	return {
		"ok": True,
		"grain": "voucher",
		"amount": amt,
		"cleared": amt <= 0.01,
		"due_date": inv.get("due_date"),
	}


def remote_account_balance(
	account: str, as_of: str | None = None, lyqd_company: str | None = None
) -> dict[str, Any]:
	from lyqd.recommendations.core import interpret_account_gl_balance

	client, company = get_remote_client(lyqd_company)
	as_of = str(getdate(as_of or today()))
	meta = _account_meta_map(client, [account])
	root = (meta.get(account) or {}).get("root_type")
	acc_name = (meta.get(account) or {}).get("account_name") or account
	signed = _sum_gl_for_account(client, company, account, as_of, as_asset=(root == "Asset"))
	interp = interpret_account_gl_balance(root, signed, acc_name)
	return {
		"ok": True,
		"grain": "account",
		"amount": interp["amount"],
		"cash_effect": interp["cash_effect"],
		"title": interp["title"],
		"cleared": interp["cleared"],
		"signed_net": interp["signed_net"],
		"due_date": None,
	}


def remote_gl_voucher_outstanding(
	source_doctype: str,
	source_name: str,
	account: str | None = None,
	as_of: str | None = None,
	lyqd_company: str | None = None,
) -> dict[str, Any]:
	client, company = get_remote_client(lyqd_company)
	as_of = str(getdate(as_of or today()))

	if source_doctype == "Purchase Receipt":
		if source_name in remote_purchase_receipts_with_invoice(client, [source_name]):
			return {
				"ok": True,
				"grain": "voucher",
				"amount": 0.0,
				"cleared": True,
				"billed": True,
			}
		# Missing PR on remote → treat as cleared
		exists = client.get_list(
			"Purchase Receipt",
			filters={"name": source_name},
			fields=["name"],
			limit_page_length=1,
		)
		if not exists:
			return {
				"ok": True,
				"grain": "voucher",
				"amount": 0.0,
				"cleared": True,
				"missing": True,
			}

	filters: dict[str, Any] = {
		"company": company,
		"is_cancelled": 0,
		"posting_date": ["<=", as_of],
	}
	if account:
		filters["account"] = account
	# Prefer against_voucher match; also try voucher_no
	rows = (
		client.get_list(
			"GL Entry",
			filters={
				**filters,
				"against_voucher_type": source_doctype,
				"against_voucher": source_name,
			},
			fields=["debit", "credit"],
			limit_page_length=500,
		)
		or []
	)
	if not rows:
		rows = (
			client.get_list(
				"GL Entry",
				filters={
					**filters,
					"voucher_type": source_doctype,
					"voucher_no": source_name,
				},
				fields=["debit", "credit"],
				limit_page_length=500,
			)
			or []
		)
	liability_amt = sum(flt(r.get("credit")) - flt(r.get("debit")) for r in rows)
	asset_amt = sum(flt(r.get("debit")) - flt(r.get("credit")) for r in rows)
	root = None
	if account:
		meta = _account_meta_map(client, [account])
		root = (meta.get(account) or {}).get("root_type")
	amt = max(flt(asset_amt if root == "Asset" else liability_amt), 0.0)
	return {
		"ok": True,
		"grain": "voucher",
		"amount": amt,
		"cleared": amt <= 0.01,
		"engine": "remote_gl",
	}
