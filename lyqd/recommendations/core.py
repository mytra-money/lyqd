"""Liability recommendations core — local ERPNext or remote site via API Key/Secret.

Payable accounts → Payment Ledger / Purchase Invoice.
Tax / other liabilities → GL open items (GST, TDS, duties, etc.).
Per-account flag controls voucher-level vs account-balance grain.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import qb
from frappe.query_builder.functions import IfNull, Sum
from frappe.utils import add_days, flt, getdate, today

from lyqd.recommendations.settings import (
	SOURCE_OTHER_SITE,
	get_integration_settings,
	is_erpnext_integration_enabled,
	is_remote_source,
)


def get_recommendation_account_rows(company: str) -> list[dict[str, Any]]:
	if not company or not frappe.db.exists("LYQD Company", company):
		return []
	return frappe.get_all(
		"LYQD Recommendation Account",
		filters={"parent": company, "parenttype": "LYQD Company"},
		fields=["account", "account_name", "show_references", "parent_account"],
	)


def _parent_account_map(company: str) -> dict[str, str]:
	"""account → parent_account for refs-off nested recommendation rows."""
	out: dict[str, str] = {}
	for row in get_recommendation_account_rows(company):
		parent = (row.get("parent_account") or "").strip()
		acc = (row.get("account") or "").strip()
		if acc and parent and not int(row.get("show_references") or 0):
			out[acc] = parent
	return out


def _find_account_grain_plan(company: str, account: str) -> str | None:
	"""Planned/Paid Account-grain Upcoming Payment for this COA account (oldest wins)."""
	if not company or not account:
		return None
	rows = frappe.get_all(
		"LYQD Upcoming Payment",
		filters={
			"company": company,
			"source_doctype": "Account",
			"source_name": account,
			"status": ("in", ["Planned", "Paid"]),
		},
		pluck="name",
		order_by="creation asc",
		limit_page_length=1,
	)
	return rows[0] if rows else None


def _dedupe_account_grain_plans(company: str) -> int:
	"""Cancel newer duplicate Account-grain plans for the same source account."""
	rows = frappe.get_all(
		"LYQD Upcoming Payment",
		filters={
			"company": company,
			"status": ("in", ["Planned", "Paid"]),
			"source_doctype": "Account",
			"source_name": ("is", "set"),
		},
		fields=["name", "source_name", "creation"],
		order_by="creation asc",
	)
	seen: set[str] = set()
	cancelled = 0
	for row in rows:
		key = row.source_name
		if key in seen:
			frappe.db.set_value(
				"LYQD Upcoming Payment",
				row.name,
				{
					"status": "Cancelled",
					"parent_payment": None,
					"notes": (frappe.db.get_value("LYQD Upcoming Payment", row.name, "notes") or "")
					+ "\nCancelled duplicate Account-grain plan",
				},
				update_modified=True,
			)
			cancelled += 1
		else:
			seen.add(key)
	return cancelled


def relink_plan_parents(company: str) -> dict[str, int]:
	"""Apply Settings parent/child nesting onto Account-grain plans.

	- Link / re-parent when child has parent_account in recommendation config
	- Unlink (clear parent_payment) when child is detached, refs turned on, or
	  the configured parent has no open plan anymore
	"""
	parent_map = _parent_account_map(company)
	linked = 0
	unlinked = 0
	rows = frappe.get_all(
		"LYQD Upcoming Payment",
		filters={
			"company": company,
			"status": ("in", ["Planned", "Paid"]),
			"source_doctype": "Account",
			"source_name": ("is", "set"),
		},
		fields=["name", "source_name", "parent_payment", "due_date", "balance_as_of"],
	)
	for row in rows:
		want_parent_acc = parent_map.get(row.source_name)
		if not want_parent_acc:
			# Detached in Settings (parent cleared / refs on / row removed from nest)
			if row.parent_payment:
				frappe.db.set_value(
					"LYQD Upcoming Payment",
					row.name,
					{"parent_payment": None},
					update_modified=True,
				)
				unlinked += 1
			continue
		parent_name = _find_account_grain_plan(company, want_parent_acc)
		if not parent_name or parent_name == row.name:
			# Parent account configured but no plan to nest under — drop stale link
			if row.parent_payment and not parent_name:
				frappe.db.set_value(
					"LYQD Upcoming Payment",
					row.name,
					{"parent_payment": None},
					update_modified=True,
				)
				unlinked += 1
			continue
		parent_meta = frappe.db.get_value(
			"LYQD Upcoming Payment",
			parent_name,
			["due_date", "balance_as_of"],
			as_dict=True,
		) or {}
		vals = {}
		if row.parent_payment != parent_name:
			vals["parent_payment"] = parent_name
		if parent_meta.get("due_date") and str(row.due_date) != str(parent_meta.due_date):
			vals["due_date"] = parent_meta.due_date
		parent_as_of = parent_meta.get("balance_as_of")
		if parent_as_of and str(row.balance_as_of or "") != str(parent_as_of):
			vals["balance_as_of"] = parent_as_of
		if vals:
			frappe.db.set_value("LYQD Upcoming Payment", row.name, vals, update_modified=True)
			linked += 1
	return {
		"linked": linked,
		"unlinked": unlinked,
		"updated": linked + unlinked,
	}


def _account_display_name(account: str) -> str:
	if not account:
		return "Account"
	if frappe.db.exists("Account", account):
		return frappe.db.get_value("Account", account, "account_name") or account
	# Remote / Data-stored account — use trailing label
	return (account.split(" - ")[0] if " - " in account else account).strip() or account


def _cash_effect_for_account(company: str, account: str) -> tuple[str, str]:
	"""Return (cash_effect, title_suffix) from Account root_type (local or remote)."""
	root = None
	acc_name = _account_display_name(account)
	if frappe.db.exists("Account", account):
		root = frappe.db.get_value("Account", account, "root_type")
	elif is_remote_source(company):
		try:
			from lyqd.recommendations import remote as remote_src

			client, _ = remote_src.get_remote_client(company)
			meta = remote_src._account_meta_map(client, [account])
			root = (meta.get(account) or {}).get("root_type")
			acc_name = (meta.get(account) or {}).get("account_name") or acc_name
		except Exception:
			frappe.log_error(title="LYQD cash_effect remote meta")
	if root == "Asset":
		return "Setoff", f"{acc_name} · setoff (asset)"
	return "Outflow", f"{acc_name} · GL balance"


def _ensure_account_grain_child_plan(
	company: str,
	account: str,
	*,
	parent_payment: str,
	due_date: str | None = None,
	balance_as_of: str | None = None,
	category: str | None = None,
) -> dict[str, Any] | None:
	"""Create a missing Account-grain plan row nested under an open parent plan."""
	if _find_account_grain_plan(company, account):
		return None
	# Re-check right before insert (concurrent Commitments loads can race)
	if frappe.db.exists(
		"LYQD Upcoming Payment",
		{
			"company": company,
			"source_doctype": "Account",
			"source_name": account,
			"status": ("in", ["Planned", "Paid"]),
		},
	):
		return None

	live = resolve_books_outstanding(
		company,
		"Account",
		account,
		as_of=balance_as_of,
	)
	if live.get("ok"):
		amt = max(flt(live.get("amount")), 0.0)
		cash_effect = live.get("cash_effect") if live.get("cash_effect") in ("Outflow", "Setoff") else None
		title = live.get("title") or None
	else:
		amt = 0.0
		cash_effect = None
		title = None
	if not cash_effect or not title:
		fallback_ce, fallback_title = _cash_effect_for_account(company, account)
		cash_effect = cash_effect or fallback_ce
		title = title or fallback_title

	doc = frappe.get_doc(
		{
			"doctype": "LYQD Upcoming Payment",
			"company": company,
			"title": title[:140],
			"category": category or "Tax",
			"due_date": due_date or today(),
			"amount": amt,
			"cash_effect": cash_effect,
			"status": "Planned",
			"notes": f"Auto-added from recommendation parent group · Account {account}",
			"source_doctype": "Account",
			"source_name": account,
			"source_account": account,
			"parent_payment": parent_payment,
			"balance_as_of": balance_as_of,
			"last_synced_on": frappe.utils.now_datetime(),
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.as_dict()


def sync_nested_account_plans(company: str) -> dict[str, Any]:
	"""
	When Settings parent/child accounts change:
	- Create missing Account-grain plan rows for children under parents that already have a plan
	- Relink / unlink parent_payment to match current recommendation nesting
	"""
	parent_map = _parent_account_map(company)
	children_of: dict[str, list[str]] = {}
	for child_acc, parent_acc in parent_map.items():
		children_of.setdefault(parent_acc, []).append(child_acc)

	created: list[str] = []
	skipped_no_parent_plan: list[str] = []

	for parent_acc, child_accs in children_of.items():
		parent_plan = _find_account_grain_plan(company, parent_acc)
		if not parent_plan:
			skipped_no_parent_plan.append(parent_acc)
			continue
		parent_meta = frappe.db.get_value(
			"LYQD Upcoming Payment",
			parent_plan,
			["due_date", "balance_as_of", "category", "status"],
			as_dict=True,
		)
		if not parent_meta or parent_meta.status not in ("Planned", "Paid"):
			continue
		for child_acc in child_accs:
			row = _ensure_account_grain_child_plan(
				company,
				child_acc,
				parent_payment=parent_plan,
				due_date=parent_meta.due_date,
				balance_as_of=parent_meta.balance_as_of,
				category=parent_meta.category or "Tax",
			)
			if row:
				created.append(row.get("name") or child_acc)

	deduped = _dedupe_account_grain_plans(company)
	relink = relink_plan_parents(company)
	return {
		"company": company,
		"created": created,
		"created_count": len(created),
		"deduped": deduped,
		"linked": relink.get("linked") or 0,
		"unlinked": relink.get("unlinked") or 0,
		"relinked": relink.get("updated") or 0,
		"parents_without_plan": skipped_no_parent_plan,
	}



def _already_accepted(company: str) -> set[tuple[str, str]]:
	rows = frappe.get_all(
		"LYQD Upcoming Payment",
		filters={
			"company": company,
			"status": ("in", ["Planned", "Paid"]),
			"source_doctype": ("is", "set"),
		},
		fields=["source_doctype", "source_name"],
	)
	return {(r.source_doctype, r.source_name) for r in rows if r.source_doctype and r.source_name}


def _classify_accounts(account_names: list[str]) -> tuple[list[str], list[str], list[str]]:
	"""Split selected accounts into payable / receivable / other (GL)."""
	if not account_names:
		return [], [], []
	meta = frappe.get_all(
		"Account",
		filters={"name": ("in", account_names)},
		fields=["name", "account_type", "root_type"],
	)
	payable, receivable, other = [], [], []
	for a in meta:
		if a.account_type == "Payable":
			payable.append(a.name)
		elif a.account_type == "Receivable":
			receivable.append(a.name)
		else:
			# Liability tax/GST, Asset ITC, Expense, etc. → GL open items / balance
			other.append(a.name)
	return payable, receivable, other


def _party_display_name(party_type: str | None, party: str | None) -> str | None:
	"""Human label for Customer / Supplier (not the link name alone)."""
	if not party:
		return None
	party_type = (party_type or "").strip()
	if party_type == "Customer" and frappe.db.exists("Customer", party):
		return frappe.db.get_value("Customer", party, "customer_name") or party
	if party_type == "Supplier" and frappe.db.exists("Supplier", party):
		return frappe.db.get_value("Supplier", party, "supplier_name") or party
	if party_type == "Employee" and frappe.db.exists("Employee", party):
		return frappe.db.get_value("Employee", party, "employee_name") or party
	return party


def _ple_voucher_rows(
	company: str,
	accounts: list[str],
	as_of: str,
	*,
	account_type: str = "Payable",
) -> list[dict[str, Any]]:
	"""Open Payment Ledger invoices for Payable (outflow) or Receivable (setoff)."""
	from erpnext.accounts.utils import QueryPaymentLedger

	if not accounts:
		return []
	is_receivable = account_type == "Receivable"
	ple = qb.DocType("Payment Ledger Entry")
	common_filter = [
		ple.company == company,
		ple.account.isin(accounts),
		ple.account_type == account_type,
	]
	posting_date = [ple.posting_date.lte(as_of)]
	rows = QueryPaymentLedger().get_voucher_outstandings(
		common_filter=common_filter,
		posting_date=posting_date,
		get_invoices=True,
		limit=100,
	)
	out = []
	for row in rows or []:
		amount = flt(row.get("outstanding_in_account_currency") or row.get("outstanding") or 0)
		if amount <= 0:
			continue
		voucher_type = row.get("voucher_type")
		voucher_no = row.get("voucher_no")
		due = row.get("due_date")
		if not due and voucher_type == "Purchase Invoice" and voucher_no:
			due = frappe.db.get_value("Purchase Invoice", voucher_no, "due_date")
		elif not due and voucher_type == "Sales Invoice" and voucher_no:
			due = frappe.db.get_value("Sales Invoice", voucher_no, "due_date")
		party = row.get("party")
		party_type = row.get("party_type")
		party_label = _party_display_name(party_type, party) or party
		title = f"{voucher_type} {voucher_no}"
		if party_label:
			title = f"{party_label} · {title}"
		if is_receivable:
			category = "Customer" if voucher_type == "Sales Invoice" else "Other"
			cash_effect = "Setoff"
		else:
			category = "Vendor" if voucher_type == "Purchase Invoice" else "Other"
			cash_effect = "Outflow"
		out.append(
			{
				"grain": "voucher",
				"account": row.get("account"),
				"source_doctype": voucher_type,
				"source_name": voucher_no,
				"title": title[:140],
				"category": category,
				"due_date": str(due) if due else None,
				"amount": amount,
				"cash_effect": cash_effect,
				"party_type": party_type,
				"party": party,
				"party_name": party_label,
				"engine": "payment_ledger",
			}
		)
	return out


def purchase_receipts_with_invoice(names: list[str]) -> set[str]:
	"""
	Purchase Receipts that already have a Purchase Invoice against them.

	Uses per_billed > 0 and/or submitted Purchase Invoice Item.purchase_receipt.
	"""
	names = [n for n in names if n]
	if not names or not frappe.db.exists("DocType", "Purchase Receipt"):
		return set()
	billed = set(
		frappe.get_all(
			"Purchase Receipt",
			filters={"name": ("in", names), "per_billed": (">", 0)},
			pluck="name",
		)
	)
	if frappe.db.exists("DocType", "Purchase Invoice Item"):
		billed.update(
			frappe.get_all(
				"Purchase Invoice Item",
				filters={"purchase_receipt": ("in", names), "docstatus": 1},
				pluck="purchase_receipt",
			)
		)
	return {n for n in billed if n}


def exclude_billed_purchase_receipts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
	"""Drop Purchase Receipt recommendations that are already billed to a Purchase Invoice."""
	pr_names = [
		i.get("source_name")
		for i in items
		if i.get("source_doctype") == "Purchase Receipt" and i.get("source_name")
	]
	if not pr_names:
		return items
	billed = purchase_receipts_with_invoice(pr_names)
	if not billed:
		return items
	return [
		i
		for i in items
		if not (
			i.get("source_doctype") == "Purchase Receipt" and i.get("source_name") in billed
		)
	]


def _gl_voucher_rows(company: str, accounts: list[str], as_of: str) -> list[dict[str, Any]]:
	"""Open GL items for Tax / TDS / GST / other non-PLE accounts.

	Aggregate by against_voucher (+ party) so Payment Entry / Journal Entry
	settlements net against the original Sales/Purchase Invoice.
	"""
	if not accounts:
		return []
	gle = qb.DocType("GL Entry")
	against_voucher_type = IfNull(gle.against_voucher_type, gle.voucher_type)
	against_voucher = IfNull(gle.against_voucher, gle.voucher_no)
	outstanding = (Sum(gle.credit) - Sum(gle.debit)).as_("outstanding")

	raw = (
		qb.from_(gle)
		.select(
			gle.account,
			gle.party_type,
			gle.party,
			against_voucher_type.as_("against_voucher_type"),
			against_voucher.as_("against_voucher"),
			outstanding,
		)
		.where(
			(gle.company == company)
			& (gle.is_cancelled == 0)
			& (gle.account.isin(accounts))
			& (gle.posting_date <= as_of)
		)
		.groupby(
			gle.account,
			gle.party_type,
			gle.party,
			against_voucher_type,
			against_voucher,
		)
		.run(as_dict=True)
	)

	# Cache root types for amount sign / cash_effect
	root_by_account = {
		a.name: a.root_type
		for a in frappe.get_all(
			"Account",
			filters={"name": ("in", accounts)},
			fields=["name", "root_type"],
		)
	}

	out = []
	for row in raw or []:
		raw_amt = flt(row.get("outstanding"))  # credit − debit
		root = root_by_account.get(row.account) or "Liability"
		if root == "Asset":
			amount = -raw_amt  # debit − credit
			cash_effect = "Setoff"
		else:
			amount = raw_amt
			cash_effect = "Outflow"
		if amount <= 0.01:
			continue
		src_dt = row.get("against_voucher_type")
		src_dn = row.get("against_voucher")
		if not src_dt or not src_dn:
			continue
		acc_name = frappe.db.get_value("Account", row.account, "account_name") or row.account
		party = row.get("party")
		party_type = row.get("party_type")
		party_label = _party_display_name(party_type, party) or party
		title = f"{acc_name} · {src_dt} {src_dn}"
		if party_label:
			title = f"{party_label} · {src_dt} {src_dn}"
		category = "Tax"
		an = (acc_name or "").lower()
		if src_dt == "Sales Invoice" or party_type == "Customer":
			category = "Customer"
		elif src_dt == "Purchase Receipt" or party_type == "Supplier":
			category = "Vendor"
		elif "tds" in an or "gst" in an or "duties" in an:
			category = "Tax"
		out.append(
			{
				"grain": "voucher",
				"account": row.account,
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
				"engine": "gl",
			}
		)
	return exclude_billed_purchase_receipts(out)


def _account_balance_rows(company: str, accounts: list[str], as_of: str) -> list[dict[str, Any]]:
	"""One recommendation line per account = net GL balance (liability outflow or asset setoff)."""
	out = []
	for account in accounts:
		root = frappe.db.get_value("Account", account, "root_type")
		acc_name = frappe.db.get_value("Account", account, "account_name") or account
		if root == "Asset":
			signed = _net_asset_gl(company, account, as_of)
			category = "Tax"
		elif root == "Liability":
			signed = _net_liability_gl(company, account, as_of)
			category = "Tax"
		else:
			# Expense / other — liability-style sign (credit − debit)
			signed = _net_liability_gl(company, account, as_of)
			category = "Other"
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
				"engine": "gl_balance",
			}
		)
	return out


def _net_liability_gl(company: str, account: str, as_of: str) -> float:
	gle = qb.DocType("GL Entry")
	row = (
		qb.from_(gle)
		.select((Sum(gle.credit) - Sum(gle.debit)).as_("outstanding"))
		.where(
			(gle.company == company)
			& (gle.is_cancelled == 0)
			& (gle.account == account)
			& (gle.posting_date <= as_of)
		)
		.run(as_dict=True)
	)
	return flt(row[0].outstanding) if row else 0.0


def _net_asset_gl(company: str, account: str, as_of: str) -> float:
	"""Debit − credit for Asset setoff balances (e.g. Input GST)."""
	gle = qb.DocType("GL Entry")
	row = (
		qb.from_(gle)
		.select((Sum(gle.debit) - Sum(gle.credit)).as_("outstanding"))
		.where(
			(gle.company == company)
			& (gle.is_cancelled == 0)
			& (gle.account == account)
			& (gle.posting_date <= as_of)
		)
		.run(as_dict=True)
	)
	return flt(row[0].outstanding) if row else 0.0


def interpret_account_gl_balance(
	root_type: str | None,
	signed_net: float,
	acc_name: str,
) -> dict[str, Any]:
	"""Map signed GL net → plan amount + cash_effect.

	Asset signed = debit − credit:
	  > 0 → Setoff (recoverable / ITC)
	  < 0 → Outflow (credit balance on asset = extra payable)
	Liability signed = credit − debit:
	  > 0 → Outflow
	  < 0 → Setoff (debit / overpayment)
	"""
	signed = flt(signed_net)
	name = (acc_name or "Account").strip() or "Account"
	if abs(signed) <= 0.01:
		# Preserve natural cash_effect for zero balances so nested stubs stay typed correctly
		zero_ce = "Setoff" if root_type == "Asset" else "Outflow"
		return {
			"amount": 0.0,
			"cash_effect": zero_ce,
			"title": f"{name} · setoff (asset)" if root_type == "Asset" else f"{name} · GL balance",
			"cleared": True,
			"signed_net": signed,
		}
	if root_type == "Asset":
		if signed > 0:
			return {
				"amount": signed,
				"cash_effect": "Setoff",
				"title": f"{name} · setoff (asset)",
				"cleared": False,
				"signed_net": signed,
			}
		return {
			"amount": abs(signed),
			"cash_effect": "Outflow",
			"title": f"{name} · credit balance (asset)",
			"cleared": False,
			"signed_net": signed,
		}
	# Liability / Expense / other (signed already credit−debit for liability helper)
	if signed > 0:
		return {
			"amount": signed,
			"cash_effect": "Outflow",
			"title": f"{name} · GL balance",
			"cleared": False,
			"signed_net": signed,
		}
	return {
		"amount": abs(signed),
		"cash_effect": "Setoff",
		"title": f"{name} · debit balance (setoff)",
		"cleared": False,
		"signed_net": signed,
	}


def get_liability_recommendations(
	company: str,
	horizon_days: int | None = None,
) -> dict[str, Any]:
	settings = get_integration_settings(company)
	if not settings.get("enabled"):
		return {
			"company": company,
			"enabled": False,
			"source": settings.get("source"),
			"items": [],
			"message": "Enable recommendations in Settings → Integrations.",
		}

	rows_cfg = get_recommendation_account_rows(company)
	if not rows_cfg:
		return {
			"company": company,
			"enabled": True,
			"source": settings.get("source"),
			"items": [],
			"message": "Select liability accounts under Settings → Recommendations.",
		}

	if horizon_days is None:
		from lyqd.cash.surplus import get_policy

		horizon_days = int(get_policy(company).get("default_forecast_horizon_days") or 30)
	horizon_days = max(int(horizon_days), 30)
	as_of = str(getdate(today()))
	horizon_end = getdate(add_days(as_of, horizon_days))

	items: list[dict[str, Any]] = []
	source = settings.get("source") or "This Site"
	# LYQD Company name may differ from ERPNext Company name on the books site
	books_company = (
		frappe.db.get_value("LYQD Company", company, "books_company") if company else None
	) or company

	try:
		if source == SOURCE_OTHER_SITE:
			from lyqd.recommendations.remote import fetch_remote_recommendation_items

			books_company = (
				frappe.db.get_value("LYQD Company", company, "books_company")
				or settings.get("remote_company")
				or company
			)
			# Account names on LYQD policy must match remote Chart of Accounts names
			items = fetch_remote_recommendation_items(
				[
					{
						"account": r.account,
						"show_references": r.show_references,
						"account_name": r.account_name,
						"parent_account": getattr(r, "parent_account", None),
					}
					for r in rows_cfg
				],
				as_of=as_of,
				lyqd_company=company,
			)
		else:
			if "erpnext" not in frappe.get_installed_apps():
				raise frappe.ValidationError(
					frappe._("This Site books require ERPNext on this site.")
				)
			ref_accounts = [r.account for r in rows_cfg if r.show_references]
			bal_accounts = [r.account for r in rows_cfg if not r.show_references]
			payable_ref, receivable_ref, other_ref = _classify_accounts(ref_accounts)
			items.extend(
				_ple_voucher_rows(books_company, payable_ref, as_of, account_type="Payable")
			)
			items.extend(
				_ple_voucher_rows(
					books_company, receivable_ref, as_of, account_type="Receivable"
				)
			)
			items.extend(_gl_voucher_rows(books_company, other_ref, as_of))
			items.extend(_account_balance_rows(books_company, bal_accounts, as_of))
			items = exclude_billed_purchase_receipts(items)
	except Exception as e:
		frappe.log_error(title="LYQD recommendations fetch failed")
		return {
			"company": company,
			"enabled": True,
			"source": source,
			"books_company": books_company,
			"items": [],
			"message": frappe._("Could not fetch recommendations: {0}").format(
				frappe.get_traceback() and str(e) or str(e)
			),
			"account_filter": [r.account for r in rows_cfg],
		}

	accepted = _already_accepted(company)
	filtered = []
	for item in items:
		key = (item["source_doctype"], item["source_name"])
		if key in accepted:
			continue
		if item.get("due_date"):
			if getdate(item["due_date"]) > horizon_end:
				continue
		filtered.append(item)

	filtered.sort(key=lambda x: (x.get("due_date") or "9999", -flt(x.get("amount"))))

	return {
		"company": company,
		"enabled": True,
		"source": source,
		"books_company": books_company,
		"horizon_days": horizon_days,
		"as_of": as_of,
		"items": filtered[:80],
		"account_filter": [r.account for r in rows_cfg],
	}


# Back-compat name used by spa.py
def get_purchase_invoice_recommendations(company: str, horizon_days: int | None = None) -> dict[str, Any]:
	return get_liability_recommendations(company, horizon_days)


def accept_recommendation(
	company: str,
	source_doctype: str,
	source_name: str,
	amount: float | None = None,
	title: str | None = None,
	category: str | None = None,
	due_date: str | None = None,
	account: str | None = None,
	cash_effect: str | None = None,
) -> dict[str, Any]:
	"""Create a Planned LYQD Upcoming Payment from a recommendation row."""
	if not is_erpnext_integration_enabled(company):
		frappe.throw(frappe._("Enable ERPNext integration before accepting recommendations"))

	existing = frappe.db.exists(
		"LYQD Upcoming Payment",
		{
			"company": company,
			"source_doctype": source_doctype,
			"source_name": source_name,
			"status": ("in", ["Planned", "Paid"]),
		},
	)
	if existing:
		return frappe.get_doc("LYQD Upcoming Payment", existing).as_dict()

	# Resolve amount/title if caller only sent keys
	if amount is None or not title:
		bundle = get_liability_recommendations(company)
		match = next(
			(
				i
				for i in bundle.get("items") or []
				if i.get("source_doctype") == source_doctype and i.get("source_name") == source_name
			),
			None,
		)
		if not match:
			frappe.throw(frappe._("Recommendation is no longer available"))
		amount = match["amount"]
		title = match["title"]
		category = category or match.get("category") or "Other"
		due_date = due_date or match.get("due_date")
		account = account or match.get("account")
		cash_effect = cash_effect or match.get("cash_effect")

	if cash_effect not in ("Outflow", "Setoff"):
		# Infer from account root when missing
		root = None
		if account and frappe.db.exists("Account", account):
			root = frappe.db.get_value("Account", account, "root_type")
		cash_effect = "Setoff" if root == "Asset" else "Outflow"

	parent_payment = None
	# Account-grain rows may nest under another refs-off recommendation account
	grain_account = account if source_doctype == "Account" else None
	if source_doctype == "Account" and source_name:
		grain_account = source_name
	if grain_account:
		want_parent = _parent_account_map(company).get(grain_account)
		if want_parent:
			parent_payment = _find_account_grain_plan(company, want_parent)
			if parent_payment:
				parent_due = frappe.db.get_value(
					"LYQD Upcoming Payment", parent_payment, "due_date"
				)
				if parent_due:
					due_date = parent_due

	doc = frappe.get_doc(
		{
			"doctype": "LYQD Upcoming Payment",
			"company": company,
			"title": (title or f"{source_doctype} {source_name}")[:140],
			"category": category or "Other",
			"due_date": due_date or today(),
			"amount": flt(amount),
			"cash_effect": cash_effect,
			"status": "Planned",
			"notes": f"Accepted from ERPNext {source_doctype} {source_name}"
			+ (f" · {account}" if account else ""),
			"source_doctype": source_doctype,
			"source_name": source_name,
			"source_account": account,
			"parent_payment": parent_payment,
			"last_synced_on": frappe.utils.now_datetime(),
		}
	)
	doc.insert()
	return doc.as_dict()



def _ple_voucher_outstanding(
	company: str,
	voucher_type: str,
	voucher_no: str,
	as_of: str,
	account: str | None = None,
	account_type: str | None = None,
) -> float:
	from erpnext.accounts.utils import QueryPaymentLedger

	ple = qb.DocType("Payment Ledger Entry")
	if not account_type and account:
		account_type = frappe.db.get_value("Account", account, "account_type")
	account_type = account_type or "Payable"
	common_filter = [
		ple.company == company,
		ple.voucher_no == voucher_no,
		ple.voucher_type == voucher_type,
		ple.account_type == account_type,
	]
	if account:
		common_filter.append(ple.account == account)
	rows = QueryPaymentLedger().get_voucher_outstandings(
		common_filter=common_filter,
		posting_date=[ple.posting_date.lte(as_of)],
		get_invoices=True,
		limit=20,
	)
	total = 0.0
	for row in rows or []:
		total += flt(row.get("outstanding_in_account_currency") or row.get("outstanding") or 0)
	return total


def _gl_voucher_outstanding(
	company: str,
	voucher_type: str,
	voucher_no: str,
	as_of: str,
	account: str | None = None,
) -> float:
	"""Net open amount for a voucher on GL. Asset accounts use debit − credit."""
	gle = qb.DocType("GL Entry")
	against_voucher_type = IfNull(gle.against_voucher_type, gle.voucher_type)
	against_voucher = IfNull(gle.against_voucher, gle.voucher_no)
	where = (
		(gle.company == company)
		& (gle.is_cancelled == 0)
		& (gle.posting_date <= as_of)
		& (
			((against_voucher_type == voucher_type) & (against_voucher == voucher_no))
			| ((gle.voucher_type == voucher_type) & (gle.voucher_no == voucher_no))
		)
	)
	if account:
		where = where & (gle.account == account)
	row = (
		qb.from_(gle)
		.select(
			(Sum(gle.credit) - Sum(gle.debit)).as_("liability_outstanding"),
			(Sum(gle.debit) - Sum(gle.credit)).as_("asset_outstanding"),
		)
		.where(where)
		.run(as_dict=True)
	)
	if not row:
		return 0.0
	root = frappe.db.get_value("Account", account, "root_type") if account else None
	if root == "Asset":
		return max(flt(row[0].asset_outstanding), 0.0)
	return max(flt(row[0].liability_outstanding), 0.0)


def resolve_books_outstanding(
	company: str,
	source_doctype: str | None,
	source_name: str | None,
	account: str | None = None,
	as_of: str | None = None,
) -> dict[str, Any]:
	"""Live outstanding for a plan row source. cleared=True means mark Paid / zero reserve."""
	as_of = str(getdate(as_of or today()))
	if not source_doctype or not source_name:
		return {"ok": False, "reason": "manual_row"}

	if is_remote_source(company):
		from lyqd.recommendations import remote as remote_src

		if source_doctype == "Account":
			return remote_src.remote_account_balance(
				source_name, as_of=as_of, lyqd_company=company
			)
		if source_doctype == "Purchase Invoice":
			return remote_src.remote_purchase_invoice_outstanding(
				source_name, lyqd_company=company
			)
		if source_doctype == "Sales Invoice":
			return remote_src.remote_sales_invoice_outstanding(
				source_name, lyqd_company=company
			)
		# Purchase Receipt (+ other vouchers): remote GL; billed PRs cleared inside helper
		return remote_src.remote_gl_voucher_outstanding(
			source_doctype,
			source_name,
			account=account,
			as_of=as_of,
			lyqd_company=company,
		)

	# —— Local site ——
	if source_doctype == "Account":
		root = frappe.db.get_value("Account", source_name, "root_type")
		acc_name = frappe.db.get_value("Account", source_name, "account_name") or source_name
		if root == "Asset":
			signed = _net_asset_gl(company, source_name, as_of)
		else:
			signed = _net_liability_gl(company, source_name, as_of)
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

	if source_doctype in ("Purchase Invoice", "Sales Invoice"):
		if not frappe.db.exists(source_doctype, source_name):
			return {
				"ok": True,
				"grain": "voucher",
				"amount": 0.0,
				"cleared": True,
				"missing": True,
			}
		inv = frappe.db.get_value(
			source_doctype,
			source_name,
			["outstanding_amount", "docstatus", "due_date", "status"],
			as_dict=True,
		)
		if inv.docstatus == 2:
			return {
				"ok": True,
				"grain": "voucher",
				"amount": 0.0,
				"cleared": True,
				"cancelled": True,
				"due_date": inv.due_date,
			}
		amt = flt(inv.outstanding_amount)
		return {
			"ok": True,
			"grain": "voucher",
			"amount": amt,
			"cleared": amt <= 0.01,
			"due_date": inv.due_date,
		}

	if source_doctype == "Purchase Receipt":
		if not frappe.db.exists("Purchase Receipt", source_name):
			return {
				"ok": True,
				"grain": "voucher",
				"amount": 0.0,
				"cleared": True,
				"missing": True,
			}
		# Once a PI exists against the PR, drop it from the books commitment
		if source_name in purchase_receipts_with_invoice([source_name]):
			return {
				"ok": True,
				"grain": "voucher",
				"amount": 0.0,
				"cleared": True,
				"billed": True,
			}
		amt = _gl_voucher_outstanding(company, source_doctype, source_name, as_of, account)
		return {
			"ok": True,
			"grain": "voucher",
			"amount": amt,
			"cleared": amt <= 0.01,
			"engine": "gl",
		}

	account_type = frappe.db.get_value("Account", account, "account_type") if account else None
	if account_type in ("Payable", "Receivable") or not account:
		amt = _ple_voucher_outstanding(
			company,
			source_doctype,
			source_name,
			as_of,
			account,
			account_type=account_type,
		)
		if amt > 0.01 or account_type in ("Payable", "Receivable"):
			return {
				"ok": True,
				"grain": "voucher",
				"amount": amt,
				"cleared": amt <= 0.01,
				"engine": "payment_ledger",
			}

	amt = _gl_voucher_outstanding(company, source_doctype, source_name, as_of, account)
	return {
		"ok": True,
		"grain": "voucher",
		"amount": amt,
		"cleared": amt <= 0.01,
		"engine": "gl",
	}


def sync_upcoming_payment_from_books(name: str, as_of: str | None = None) -> dict[str, Any]:
	"""Refresh one Planned (or reopenable) Upcoming Payment from ERPNext books.

	Account-grain rows with ``balance_as_of`` always sync GL as of that date
	(month-end GST/TDS), not today — unless ``as_of`` is passed explicitly.
	"""
	doc = frappe.get_doc("LYQD Upcoming Payment", name)
	if not is_erpnext_integration_enabled(doc.company):
		frappe.throw(frappe._("Enable ERPNext integration to sync from books"))

	if doc.status not in ("Planned", "Paid"):
		return {"name": name, "action": "skipped", "reason": "status"}

	sync_as_of = as_of or getattr(doc, "balance_as_of", None) or None
	live = resolve_books_outstanding(
		doc.company,
		doc.source_doctype,
		doc.source_name,
		account=getattr(doc, "source_account", None),
		as_of=sync_as_of,
	)
	if not live.get("ok"):
		return {"name": name, "action": "skipped", "reason": live.get("reason") or "no_source"}

	prev_amount = flt(doc.amount)
	prev_status = doc.status
	action = "unchanged"
	grain = live.get("grain") or ("account" if doc.source_doctype == "Account" else "voucher")

	if live.get("cancelled") or live.get("missing"):
		doc.status = "Cancelled"
		doc.amount = 0
		action = "cancelled"
	elif grain == "account":
		# GL balance grain (e.g. TDS / GST): no ERPNext "Paid"; keep Planned.
		# Amount is absolute; cash_effect flips for asset credit / liability debit balances.
		new_amt = max(flt(live.get("amount")), 0.0)
		new_ce = live.get("cash_effect")
		ce_changed = new_ce in ("Outflow", "Setoff") and doc.cash_effect != new_ce
		if ce_changed:
			doc.cash_effect = new_ce
		if live.get("title") and live.get("signed_net") is not None:
			# Keep title in sync when balance flips debit↔credit
			doc.title = str(live["title"])[:140]
		if doc.status != "Planned":
			doc.status = "Planned"
			doc.amount = new_amt
			action = "reopened" if prev_status != "Planned" else "amount_updated"
		elif abs(new_amt - prev_amount) > 0.01 or ce_changed:
			doc.amount = new_amt
			action = "amount_updated"
	elif live.get("cleared"):
		# Voucher grain: outstanding 0 in books → Paid on the plan (still LYQD-only status)
		if doc.status != "Paid":
			doc.status = "Paid"
			action = "marked_paid"
		if prev_amount <= 0 and live.get("amount") is not None:
			doc.amount = flt(live["amount"]) or prev_amount
	else:
		new_amt = flt(live.get("amount"))
		if doc.status == "Paid" and new_amt > 0.01:
			doc.status = "Planned"
			doc.amount = new_amt
			action = "reopened"
		elif abs(new_amt - prev_amount) > 0.01:
			doc.amount = new_amt
			doc.status = "Planned"
			action = "amount_updated"
		elif doc.status != "Planned":
			doc.status = "Planned"
			action = "status_updated"

		if live.get("due_date") and doc.source_doctype in ("Purchase Invoice", "Sales Invoice"):
			doc.due_date = live["due_date"]
		elif live.get("due_date") and not doc.due_date:
			doc.due_date = live["due_date"]

	doc.last_synced_on = frappe.utils.now_datetime()
	doc.save(ignore_permissions=True)

	return {
		"name": name,
		"action": action,
		"status": doc.status,
		"amount": flt(doc.amount),
		"previous_amount": prev_amount,
		"previous_status": prev_status,
		"live_amount": flt(live.get("amount")),
		"grain": grain,
		"balance_as_of": str(doc.balance_as_of) if getattr(doc, "balance_as_of", None) else None,
		"as_of_used": str(getdate(sync_as_of)) if sync_as_of else str(getdate(today())),
	}


def default_balance_as_of_for_due(due_date: str | None = None) -> str:
	"""Last day of the calendar month before the due date (GST/TDS month-end)."""
	from frappe.utils import add_months, get_last_day

	d = getdate(due_date or today())
	return str(get_last_day(add_months(d, -1)))


def set_upcoming_balance_as_of(
	name: str,
	as_of: str | None,
	*,
	cascade_children: bool = True,
	sync: bool = True,
) -> dict[str, Any]:
	"""Freeze (or clear) GL balance date on a plan row; optionally refresh amounts."""
	doc = frappe.get_doc("LYQD Upcoming Payment", name)
	frappe.only_for(("System Manager", "LYQD Manager", "LYQD User"))

	as_of_s = str(getdate(as_of)) if as_of else None
	targets = [doc.name]
	if cascade_children and not doc.parent_payment:
		targets.extend(
			frappe.get_all(
				"LYQD Upcoming Payment",
				filters={"parent_payment": doc.name, "status": ("in", ["Planned", "Paid"])},
				pluck="name",
			)
		)

	for target in targets:
		frappe.db.set_value(
			"LYQD Upcoming Payment",
			target,
			"balance_as_of",
			as_of_s,
			update_modified=True,
		)

	results = []
	if sync and is_erpnext_integration_enabled(doc.company):
		for target in targets:
			row = frappe.get_doc("LYQD Upcoming Payment", target)
			if row.source_doctype and row.source_name:
				results.append(sync_upcoming_payment_from_books(target, as_of=as_of_s))

	return {
		"name": name,
		"balance_as_of": as_of_s,
		"updated": targets,
		"synced": results,
	}


def sync_planned_from_books(company: str) -> dict[str, Any]:
	"""
	Sync all ERPNext-sourced Planned (and Paid-with-source) Upcoming Payments for a company.

	- Voucher outstanding 0 → mark Paid
	- Voucher cancelled/missing → Cancelled
	- Amount drift → update amount
	- Account-grain → refresh from GL as of balance_as_of (or today if unset)
	"""
	if not is_erpnext_integration_enabled(company):
		return {
			"company": company,
			"enabled": False,
			"results": [],
			"message": "ERPNext integration is off.",
		}

	rows = frappe.get_all(
		"LYQD Upcoming Payment",
		filters={
			"company": company,
			"status": ("in", ["Planned", "Paid"]),
			"source_doctype": ("is", "set"),
			"source_name": ("is", "set"),
		},
		pluck="name",
	)
	results = []
	for name in rows:
		results.append(sync_upcoming_payment_from_books(name))

	nested = sync_nested_account_plans(company)

	summary = {
		"marked_paid": sum(1 for r in results if r.get("action") == "marked_paid"),
		"amount_updated": sum(1 for r in results if r.get("action") == "amount_updated"),
		"cancelled": sum(1 for r in results if r.get("action") == "cancelled"),
		"reopened": sum(1 for r in results if r.get("action") == "reopened"),
		"unchanged": sum(1 for r in results if r.get("action") == "unchanged"),
		"skipped": sum(1 for r in results if r.get("action") == "skipped"),
		"parents_relinked": nested.get("relinked") or 0,
		"children_created": nested.get("created_count") or 0,
		"children_unlinked": nested.get("unlinked") or 0,
	}
	return {
		"company": company,
		"enabled": True,
		"synced": len(results),
		"summary": summary,
		"results": results,
	}
