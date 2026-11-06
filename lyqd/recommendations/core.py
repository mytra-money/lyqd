"""Liability recommendations core — local ERPNext or remote site via API Key/Secret.

Payable accounts → Payment Ledger / Purchase Invoice.
Tax / other liabilities → GL open items (GST, TDS, duties, etc.).
Per-account flag controls voucher-level vs account-balance grain.
"""

from __future__ import annotations

import re
from typing import Any

import frappe
from frappe import qb
from frappe.query_builder.functions import IfNull, Sum
from frappe.utils import add_days, flt, getdate, today

# Trailing `` · 1/3`` / `` · 2/4`` markers — display-only; not stored on titles.
_SPLIT_INDEX_SUFFIX_RE = re.compile(r"(?:\s*·\s*\d+\s*/\s*\d+)+\s*$", re.UNICODE)


def _strip_split_index_suffix(title: str | None) -> str:
	"""Remove stacked installment suffixes so re-split keeps a clean base title."""
	return _SPLIT_INDEX_SUFFIX_RE.sub("", (title or "").strip()).strip()

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
				if _root_has_splits(row.parent_payment):
					# Keep nest while root schedule exists — Settings detach waits on Merge
					continue
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
				if _root_has_splits(row.parent_payment):
					continue
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
		return "Inflow", f"{acc_name} · receivable / asset"
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
		cash_effect = (
			live.get("cash_effect")
			if live.get("cash_effect") in ("Outflow", "Setoff", "Inflow")
			else None
		)
		if cash_effect == "Setoff":
			cash_effect = "Inflow"
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



# Synthetic Payment Schedule / Split child ids on LYQD Upcoming Payment.source_row
LYQD_SPLIT_PREFIX = "lyqd-split-"


def _is_lyqd_split_row(source_row: str | None) -> bool:
	return bool(source_row) and str(source_row).startswith(LYQD_SPLIT_PREFIX)


def _already_accepted(company: str) -> set[tuple[str, str, str]]:
	"""Accepted / ignored keys: (source_doctype, source_name, source_row).

	New accepts store empty ``source_row`` (SI/PI + Account). Legacy installment /
	``lyqd-split-N`` rows may still have a key; any accept for a voucher also
	covers the blank-row key so From-books hides the whole voucher.

	``Ignored`` rows stay hidden from recommendations until the user restores them.
	"""
	rows = frappe.get_all(
		"LYQD Upcoming Payment",
		filters={
			"company": company,
			"status": ("in", ["Planned", "Paid", "Ignored"]),
			"source_doctype": ("is", "set"),
		},
		fields=["source_doctype", "source_name", "source_row"],
	)
	out: set[tuple[str, str, str]] = set()
	for r in rows:
		if not r.source_doctype or not r.source_name:
			continue
		out.add((r.source_doctype, r.source_name, (r.source_row or "").strip()))
		# One plan per voucher/account hides further books suggestions
		out.add((r.source_doctype, r.source_name, ""))
	return out


def _lyqd_split_covered_sources(company: str) -> set[tuple[str, str]]:
	"""(source_doctype, source_name) that already have a Split schedule — hide books suggestions."""
	covered: set[tuple[str, str]] = set()
	legacy = frappe.get_all(
		"LYQD Upcoming Payment",
		filters={
			"company": company,
			"status": ("in", ["Planned", "Paid"]),
			"source_doctype": ("is", "set"),
			"source_row": ("like", f"{LYQD_SPLIT_PREFIX}%"),
		},
		fields=["source_doctype", "source_name"],
	)
	for r in legacy:
		if r.source_doctype and r.source_name:
			covered.add((r.source_doctype, r.source_name))

	if frappe.db.exists("DocType", "LYQD Upcoming Split"):
		parents = frappe.get_all(
			"LYQD Upcoming Split",
			filters={"parenttype": "LYQD Upcoming Payment"},
			fields=["parent"],
			distinct=True,
		)
		names = [p.parent for p in parents if p.parent]
		if names:
			for r in frappe.get_all(
				"LYQD Upcoming Payment",
				filters={
					"name": ("in", names),
					"company": company,
					"status": ("in", ["Planned", "Paid"]),
					"source_doctype": ("is", "set"),
				},
				fields=["source_doctype", "source_name"],
			):
				if r.source_doctype and r.source_name:
					covered.add((r.source_doctype, r.source_name))
	return covered


def _nested_account_child_plans(root) -> list[Any]:
	"""Planned/Paid Account-grain children nested under a nest root."""
	if getattr(root, "parent_payment", None):
		return []
	return frappe.get_all(
		"LYQD Upcoming Payment",
		filters={
			"parent_payment": root.name,
			"status": ("in", ["Planned", "Paid"]),
			"source_doctype": "Account",
		},
		fields=[
			"name",
			"title",
			"status",
			"amount",
			"due_date",
			"cash_effect",
			"source_doctype",
			"source_name",
			"source_account",
			"balance_as_of",
		],
	)


def _books_amount_for_plan_row(row, *, as_of: str | None = None) -> float | None:
	"""Live books amount for one Account/voucher plan row, or None if unavailable."""
	src_dt = getattr(row, "source_doctype", None) or (row.get("source_doctype") if isinstance(row, dict) else None)
	src_name = getattr(row, "source_name", None) or (row.get("source_name") if isinstance(row, dict) else None)
	company = getattr(row, "company", None)
	if not company and hasattr(row, "name"):
		company = frappe.db.get_value("LYQD Upcoming Payment", row.name, "company")
	if not src_dt or not src_name or not company:
		return None
	account = (
		getattr(row, "source_account", None)
		or getattr(row, "source_name", None)
		or (row.get("source_account") if isinstance(row, dict) else None)
	)
	try:
		live = resolve_books_outstanding(
			company,
			src_dt,
			src_name,
			account=account if src_dt == "Account" else getattr(row, "source_account", None),
			as_of=as_of,
		)
	except Exception:
		frappe.log_error(title="LYQD group-net books lookup")
		return None
	if not live.get("ok") or live.get("missing") or live.get("cancelled"):
		return None
	return max(flt(live.get("amount")), 0.0)


def _cash_effect_sign(effect: str | None) -> float:
	"""Outflow reserves (+); Inflow / Setoff credits (−) — same as free-cash / nest UI."""
	if (effect or "Outflow") in ("Inflow", "Setoff"):
		return -1.0
	return 1.0


def _signed_plan_amount(row) -> float:
	amt = flt(getattr(row, "amount", None) if not isinstance(row, dict) else row.get("amount"))
	effect = (
		getattr(row, "cash_effect", None)
		if not isinstance(row, dict)
		else row.get("cash_effect")
	)
	return amt * _cash_effect_sign(effect)


def compute_upcoming_group_net(name: str) -> float | None:
	"""Signed nest total for an Account-group root, or None when not a nest.

	Outflow +, Inflow/Setoff − — same sign convention as Commitments ``_groupNet``.
	Root ``amount`` stays the parent's own grain; this is parent + nested children.
	"""
	if not name:
		return None
	row = frappe.db.get_value(
		"LYQD Upcoming Payment",
		name,
		["name", "amount", "cash_effect", "status", "parent_payment"],
		as_dict=True,
	)
	if not row or row.parent_payment:
		return None
	children = frappe.get_all(
		"LYQD Upcoming Payment",
		filters={
			"parent_payment": name,
			"status": ("in", ["Planned", "Paid"]),
		},
		fields=["amount", "cash_effect", "status"],
	)
	if not children:
		return None
	net = 0.0
	if (row.status or "Planned") in ("Planned", "Paid"):
		net += _signed_plan_amount(row)
	for child in children:
		net += _signed_plan_amount(child)
	return flt(net, 2)


def refresh_upcoming_group_net(name: str | None) -> float | None:
	"""Persist ``group_net`` on a nest root (or 0 when not a nest). Safe from hooks.

	Currency columns are NOT NULL in MariaDB — use 0 for children / non-nest roots.
	"""
	if not name:
		return None
	if not frappe.db.exists("LYQD Upcoming Payment", name):
		return None
	# Nested rows never own group_net
	if frappe.db.get_value("LYQD Upcoming Payment", name, "parent_payment"):
		if flt(frappe.db.get_value("LYQD Upcoming Payment", name, "group_net")) != 0:
			frappe.db.set_value(
				"LYQD Upcoming Payment",
				name,
				"group_net",
				0,
				update_modified=False,
			)
		return None
	net = compute_upcoming_group_net(name)
	# Non-nest root → 0; nest root → signed total (may itself be 0.00)
	value = 0.0 if net is None else flt(net, 2)
	current = flt(frappe.db.get_value("LYQD Upcoming Payment", name, "group_net"))
	if abs(current - value) < 0.005:
		return value if net is not None else None
	frappe.db.set_value(
		"LYQD Upcoming Payment",
		name,
		"group_net",
		value,
		update_modified=False,
	)
	return value if net is not None else None


def _group_net_basis(doc, family: list[Any] | None = None) -> tuple[float, str]:
	"""Split / refresh basis for a nest root = **signed** group net (not sum of absolutes).

	Matches Commitments nest ``_groupNet``: Outflow +, Inflow/Setoff −.
	Only a positive net (cash still reserved) is used as a Split total.

	For **Split open**, prefer the plan nest total already on screen (esp. when
	frozen) so the dialog does not jump to a different live-GL figure. Live books
	drift is handled on Refresh → Adjust split.
	"""
	family = family if family is not None else _split_replace_family(doc)
	children = _nested_account_child_plans(doc) if doc.source_doctype == "Account" else []

	if doc.source_doctype == "Account" and children:
		stored = getattr(doc, "group_net", None)
		if stored is None or stored == "":
			stored = frappe.db.get_value("LYQD Upcoming Payment", doc.name, "group_net")
		# Prefer persisted nest total when the root actually has children
		if stored is not None and stored != "" and flt(stored) > 0.01:
			return flt(stored, 2), "plan_group"
		plan_net = flt(
			_signed_plan_amount(doc) + sum(_signed_plan_amount(c) for c in children),
			2,
		)
		if plan_net > 0.01:
			return plan_net, "plan_group"
		# Net credit / zero — try live signed books for transparency
		signed_parts: list[float] = []
		ok_books = True
		for row in [doc, *children]:
			live_amt = _books_amount_for_plan_row(
				row if row is not doc else doc,
				as_of=getattr(doc, "balance_as_of", None),
			)
			if live_amt is None:
				ok_books = False
				break
			effect = getattr(row, "cash_effect", None) or "Outflow"
			signed_parts.append(flt(live_amt) * _cash_effect_sign(effect))
		if ok_books:
			net = flt(sum(signed_parts), 2)
			if net > 0.01:
				return net, "books_group"
	return _split_basis_amount_single(doc, family)


def _split_basis_amount_single(doc, family: list[Any]) -> tuple[float, str]:
	"""Amount for one voucher/account (no nest rollup)."""
	family_sum = sum(flt(r.amount) for r in family)
	if doc.source_doctype == "Account" and doc.source_name:
		try:
			live = resolve_books_outstanding(
				doc.company,
				"Account",
				doc.source_name,
				account=doc.source_name,
				as_of=None,
			)
			if live.get("ok") and not live.get("missing") and not live.get("cancelled"):
				books = max(flt(live.get("amount")), 0.0)
				if books > 0.01:
					return books, "books"
		except Exception:
			frappe.log_error(title="LYQD split basis books lookup")
	if doc.source_doctype in ("Purchase Invoice", "Sales Invoice") and doc.source_name:
		try:
			live = resolve_books_outstanding(
				doc.company,
				doc.source_doctype,
				doc.source_name,
				account=getattr(doc, "source_account", None),
				as_of=None,
			)
			if live.get("ok") and not live.get("missing") and not live.get("cancelled"):
				books = max(flt(live.get("amount")), 0.0)
				if books > 0.01:
					return books, "books"
		except Exception:
			frappe.log_error(title="LYQD voucher split basis books lookup")
	if family_sum > 0.01:
		return family_sum, "plan_family"
	return flt(doc.amount), "row"


def _payment_schedule_rows(
	voucher_type: str,
	voucher_no: str,
	*,
	lyqd_company: str | None = None,
) -> list[dict[str, Any]]:
	"""Payment Schedule child rows for a PI/SI (local or remote books)."""
	fields = [
		"name",
		"due_date",
		"payment_term",
		"description",
		"payment_amount",
		"outstanding",
		"paid_amount",
		"base_payment_amount",
		"base_outstanding",
		"idx",
	]
	if lyqd_company and is_remote_source(lyqd_company):
		from lyqd.recommendations.remote import get_remote_client

		client, _books = get_remote_client(lyqd_company)
		# Child DocType get_list often PermissionError on remote sites — read from parent.
		try:
			doc = client.get_doc(voucher_type, voucher_no) or {}
			rows = doc.get("payment_schedule") or []
			# Normalize to field dicts (get_doc returns full child rows)
			return [
				{k: r.get(k) for k in fields}
				for r in rows
				if isinstance(r, dict)
			]
		except Exception:
			frappe.log_error(title="LYQD remote payment schedule")
			return []
	if not frappe.db.exists("DocType", "Payment Schedule"):
		return []
	return frappe.get_all(
		"Payment Schedule",
		filters={
			"parenttype": voucher_type,
			"parent": voucher_no,
			"parentfield": "payment_schedule",
		},
		fields=fields,
		order_by="idx asc",
	)


def expand_payment_schedule_item(
	item: dict[str, Any],
	*,
	lyqd_company: str | None = None,
) -> list[dict[str, Any]]:
	"""One From-books suggestion per voucher.

	Payment Schedule is only used later to *seed* the splits table preview —
	not to create separate suggestion rows or ``source_row`` keys.
	"""
	# lyqd_company kept for call-site compatibility
	_ = lyqd_company
	item = dict(item)
	item.pop("source_row", None)
	return [item]


def _payment_schedule_seed_rows(
	voucher_type: str,
	voucher_no: str,
	*,
	basis: float,
	title: str,
	lyqd_company: str | None = None,
	due_date: str | None = None,
) -> list[dict[str, Any]]:
	"""Build split preview rows from ERPNext Payment Schedule (suggestion only)."""
	sched = _payment_schedule_rows(voucher_type, voucher_no, lyqd_company=lyqd_company)
	if len(sched) < 2:
		return []
	parts: list[dict[str, Any]] = []
	for row in sched:
		base_out = flt(row.get("base_outstanding"))
		party_out = flt(row.get("outstanding"))
		base_pay = flt(row.get("base_payment_amount")) or flt(row.get("payment_amount"))
		paid = flt(row.get("paid_amount"))
		amt = base_out if base_out > 0.01 else party_out
		if amt <= 0.01:
			if paid >= flt(row.get("payment_amount")) - 0.01 and paid > 0:
				continue
			amt = base_pay
		if amt <= 0.01:
			continue
		due = row.get("due_date")
		# Keep base title only — installment index / payment-term is UI display, not field value
		parts.append(
			{
				"due_date": str(due) if due else (due_date or today()),
				"amount": amt,
				"title": _strip_split_index_suffix(title)[:140],
			}
		)
	total = sum(flt(p["amount"]) for p in parts)
	if not parts or total <= 0.01 or basis <= 0.01:
		return []
	factor = basis / total
	for p in parts:
		p["amount"] = flt(p["amount"] * factor, 2)
	parts = [p for p in parts if flt(p["amount"]) > 0.01]
	drift = flt(basis - sum(flt(p["amount"]) for p in parts), 2)
	if parts and abs(drift) >= 0.01:
		parts[-1]["amount"] = flt(parts[-1]["amount"] + drift, 2)
	return parts


def _installment_outstanding(
	voucher_type: str,
	voucher_no: str,
	source_row: str,
	invoice_outstanding: float,
	*,
	lyqd_company: str | None = None,
) -> dict[str, Any]:
	"""Outstanding for one Payment Schedule row, clamped to invoice outstanding."""
	sched = _payment_schedule_rows(voucher_type, voucher_no, lyqd_company=lyqd_company)
	row = next((r for r in sched if r.get("name") == source_row), None)
	if not row:
		return {
			"ok": True,
			"grain": "voucher_installment",
			"amount": 0.0,
			"cleared": True,
			"missing": True,
			"due_date": None,
		}
	base_out = flt(row.get("base_outstanding"))
	party_out = flt(row.get("outstanding"))
	amt = base_out if base_out > 0.01 else party_out
	if amt <= 0.01:
		paid = flt(row.get("paid_amount"))
		pay = flt(row.get("payment_amount"))
		if paid >= pay - 0.01 and paid > 0:
			amt = 0.0
		else:
			# Scale this row's share of remaining invoice outstanding
			base_pay = flt(row.get("base_payment_amount")) or pay
			total_pay = sum(
				flt(r.get("base_payment_amount")) or flt(r.get("payment_amount")) for r in sched
			)
			if total_pay > 0.01 and invoice_outstanding > 0.01:
				amt = flt(invoice_outstanding * (base_pay / total_pay), 2)
			else:
				amt = 0.0
	amt = min(amt, max(flt(invoice_outstanding), 0.0))
	return {
		"ok": True,
		"grain": "voucher_installment",
		"amount": amt,
		"cleared": amt <= 0.01,
		"due_date": row.get("due_date"),
		"source_row": source_row,
	}


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
	"""Open Payment Ledger invoices for Payable (outflow) or Receivable (incoming)."""
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
		# Prefer company-currency outstanding (not account-currency USD/EUR/…).
		amount = flt(row.get("outstanding") or 0)
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
			cash_effect = "Inflow"
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
			cash_effect = "Inflow"
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
	  > 0 → Inflow (receivable / recoverable asset — Incoming, not free cash)
	  < 0 → Outflow (credit balance on asset = extra payable)
	Liability signed = credit − debit:
	  > 0 → Outflow
	  < 0 → Inflow (debit / overpayment — Incoming)
	"""
	signed = flt(signed_net)
	name = (acc_name or "Account").strip() or "Account"
	if abs(signed) <= 0.01:
		# Preserve natural cash_effect for zero balances so nested stubs stay typed correctly
		zero_ce = "Inflow" if root_type == "Asset" else "Outflow"
		return {
			"amount": 0.0,
			"cash_effect": zero_ce,
			"title": f"{name} · receivable / asset" if root_type == "Asset" else f"{name} · GL balance",
			"cleared": True,
			"signed_net": signed,
		}
	if root_type == "Asset":
		if signed > 0:
			return {
				"amount": signed,
				"cash_effect": "Inflow",
				"title": f"{name} · receivable / asset",
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
		"cash_effect": "Inflow",
		"title": f"{name} · debit balance (incoming)",
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
	split_covered = _lyqd_split_covered_sources(company)
	parent_map = _parent_account_map(company)
	filtered = []
	for raw in items:
		# PI/SI with multiple due dates → one suggestion per open installment
		# (same shape as LYQD Split: one plan row per due).
		# Never let schedule expand kill the whole From-books column.
		try:
			expanded = expand_payment_schedule_item(raw, lyqd_company=company)
		except Exception:
			frappe.log_error(title="LYQD expand payment schedule")
			expanded = [raw]
		for item in expanded:
			src_dt = item.get("source_doctype") or ""
			src_name = item.get("source_name") or ""
			if (src_dt, src_name) in split_covered:
				continue
			key = (src_dt, src_name, (item.get("source_row") or "").strip())
			if key in accepted:
				continue
			# Legacy whole-invoice accept should hide all installments of that voucher
			if item.get("source_row") and (src_dt, src_name, "") in accepted:
				continue
			if item.get("due_date"):
				if getdate(item["due_date"]) > horizon_end:
					continue
			# Nest Account-grain suggestions the same way as the plan (Settings parent_account)
			if item.get("source_doctype") == "Account":
				acc = item.get("source_name") or item.get("account")
				item["parent_account"] = parent_map.get(acc) or None
			else:
				item["parent_account"] = None
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


def _resolve_recommendation_fields(
	company: str,
	source_doctype: str,
	source_name: str,
	*,
	amount: float | None = None,
	title: str | None = None,
	category: str | None = None,
	due_date: str | None = None,
	account: str | None = None,
	cash_effect: str | None = None,
) -> dict[str, Any]:
	"""Fill missing accept/ignore fields from the live recommendation bundle."""
	if amount is None or not title:
		bundle = get_liability_recommendations(company)
		match = next(
			(
				i
				for i in bundle.get("items") or []
				if i.get("source_doctype") == source_doctype
				and i.get("source_name") == source_name
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

	if cash_effect not in ("Outflow", "Setoff", "Inflow"):
		if source_doctype == "Sales Invoice":
			cash_effect = "Inflow"
		else:
			root = None
			if account and frappe.db.exists("Account", account):
				root = frappe.db.get_value("Account", account, "root_type")
			cash_effect = "Inflow" if root == "Asset" else "Outflow"
	# Legacy Setoff (asset / SI) → Incoming
	if cash_effect == "Setoff":
		cash_effect = "Inflow"

	return {
		"amount": flt(amount),
		"title": (title or f"{source_doctype} {source_name}")[:140],
		"category": category or "Other",
		"due_date": due_date or today(),
		"account": account,
		"cash_effect": cash_effect,
	}


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
	source_row: str | None = None,
	probability: float | int | None = None,
) -> dict[str, Any]:
	"""Create a Planned LYQD Upcoming Payment from a recommendation row."""
	if not is_erpnext_integration_enabled(company):
		frappe.throw(frappe._("Enable ERPNext integration before accepting recommendations"))

	# One plan per voucher/account — ignore legacy source_row on accept
	existing = frappe.db.get_value(
		"LYQD Upcoming Payment",
		{
			"company": company,
			"source_doctype": source_doctype,
			"source_name": source_name,
			"status": ("in", ["Planned", "Paid"]),
		},
		"name",
		order_by="creation asc",
	)
	if existing:
		return frappe.get_doc("LYQD Upcoming Payment", existing).as_dict()

	# Previously ignored → restore to Planned with fresh books fields
	ignored = frappe.db.get_value(
		"LYQD Upcoming Payment",
		{
			"company": company,
			"source_doctype": source_doctype,
			"source_name": source_name,
			"status": "Ignored",
		},
		"name",
		order_by="creation asc",
	)

	fields = _resolve_recommendation_fields(
		company,
		source_doctype,
		source_name,
		amount=amount,
		title=title,
		category=category,
		due_date=due_date,
		account=account,
		cash_effect=cash_effect,
	)
	cash_effect = fields["cash_effect"]
	amount = fields["amount"]
	title = fields["title"]
	category = fields["category"]
	due_date = fields["due_date"]
	account = fields["account"]

	prob = 100
	if cash_effect == "Inflow":
		prob = min(max(flt(probability if probability is not None else 100), 0), 100)

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

	if ignored:
		doc = frappe.get_doc("LYQD Upcoming Payment", ignored)
		doc.title = title
		doc.category = category
		doc.due_date = due_date
		doc.amount = amount
		doc.cash_effect = cash_effect
		doc.probability = prob
		doc.status = "Planned"
		doc.notes = f"Restored from ignored · ERPNext {source_doctype} {source_name}" + (
			f" · {account}" if account else ""
		)
		doc.source_row = None
		doc.source_account = account
		doc.parent_payment = parent_payment
		doc.last_synced_on = frappe.utils.now_datetime()
		doc.save()
		return doc.as_dict()

	doc = frappe.get_doc(
		{
			"doctype": "LYQD Upcoming Payment",
			"company": company,
			"title": title,
			"category": category,
			"due_date": due_date,
			"amount": amount,
			"cash_effect": cash_effect,
			"probability": prob,
			"status": "Planned",
			"notes": f"Accepted from ERPNext {source_doctype} {source_name}"
			+ (f" · {account}" if account else ""),
			"source_doctype": source_doctype,
			"source_name": source_name,
			"source_row": None,
			"source_account": account,
			"parent_payment": parent_payment,
			"last_synced_on": frappe.utils.now_datetime(),
		}
	)
	doc.insert()

	# SI/PI with multi-due Payment Schedule → seed splits table (suggestion applied)
	if source_doctype in ("Purchase Invoice", "Sales Invoice") and source_name:
		seed = _payment_schedule_seed_rows(
			source_doctype,
			source_name,
			basis=flt(doc.amount),
			title=doc.title,
			lyqd_company=company,
			due_date=str(doc.due_date) if doc.due_date else None,
		)
		if len(seed) >= 2:
			apply_gl_split_schedule(
				doc.name, seed, basis=flt(doc.amount), basis_source="books"
			)
			return frappe.get_doc("LYQD Upcoming Payment", doc.name).as_dict()

	return doc.as_dict()


def ignore_recommendation(
	company: str,
	source_doctype: str,
	source_name: str,
	amount: float | None = None,
	title: str | None = None,
	category: str | None = None,
	due_date: str | None = None,
	account: str | None = None,
	cash_effect: str | None = None,
	source_row: str | None = None,
) -> dict[str, Any]:
	"""Hide a From-books suggestion by storing an Ignored Upcoming Payment.

	Ignored rows do not reserve free cash and stay out of recommendations until
	the user adds them to the plan (or deletes / cancels the ignored row).
	"""
	_ = source_row  # legacy; one ignore per voucher/account
	if not is_erpnext_integration_enabled(company):
		frappe.throw(frappe._("Enable ERPNext integration before ignoring recommendations"))
	frappe.only_for(("System Manager", "LYQD Manager", "LYQD User"))

	if not source_doctype or not source_name:
		frappe.throw(frappe._("source_doctype and source_name are required"))

	# Already on plan — do not replace Planned/Paid with Ignored
	existing = frappe.db.get_value(
		"LYQD Upcoming Payment",
		{
			"company": company,
			"source_doctype": source_doctype,
			"source_name": source_name,
			"status": ("in", ["Planned", "Paid"]),
		},
		"name",
		order_by="creation asc",
	)
	if existing:
		frappe.throw(
			frappe._(
				"{0} is already on the plan as {1}. Edit or cancel that row instead of ignoring."
			).format(source_name, existing)
		)

	ignored = frappe.db.get_value(
		"LYQD Upcoming Payment",
		{
			"company": company,
			"source_doctype": source_doctype,
			"source_name": source_name,
			"status": "Ignored",
		},
		"name",
		order_by="creation asc",
	)
	if ignored:
		return frappe.get_doc("LYQD Upcoming Payment", ignored).as_dict()

	fields = _resolve_recommendation_fields(
		company,
		source_doctype,
		source_name,
		amount=amount,
		title=title,
		category=category,
		due_date=due_date,
		account=account,
		cash_effect=cash_effect,
	)

	doc = frappe.get_doc(
		{
			"doctype": "LYQD Upcoming Payment",
			"company": company,
			"title": fields["title"],
			"category": fields["category"],
			"due_date": fields["due_date"],
			"amount": fields["amount"],
			"cash_effect": fields["cash_effect"],
			"probability": 100,
			"status": "Ignored",
			"notes": f"Ignored from ERPNext {source_doctype} {source_name}"
			+ (f" · {fields['account']}" if fields.get("account") else ""),
			"source_doctype": source_doctype,
			"source_name": source_name,
			"source_row": None,
			"source_account": fields.get("account"),
			"parent_payment": None,
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
		# Company currency — never outstanding_in_account_currency (USD/EUR/…).
		total += flt(row.get("outstanding") or 0)
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
	source_row: str | None = None,
) -> dict[str, Any]:
	"""Live outstanding for a plan row source. cleared=True means mark Paid / zero reserve."""
	as_of = str(getdate(as_of or today()))
	source_row = (source_row or "").strip() or None
	if not source_doctype or not source_name:
		return {"ok": False, "reason": "manual_row"}

	if is_remote_source(company):
		from lyqd.recommendations import remote as remote_src

		if source_doctype == "Account":
			return remote_src.remote_account_balance(
				source_name, as_of=as_of, lyqd_company=company
			)
		if source_doctype == "Purchase Invoice":
			# Installment / Split rows share voucher outstanding — allocate on sync.
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
		from lyqd.fx import get_lyqd_company_currency, invoice_outstanding_in_company_currency

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
			[
				"outstanding_amount",
				"docstatus",
				"due_date",
				"status",
				"currency",
				"party_account_currency",
				"conversion_rate",
				"posting_date",
			],
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
		books_company = (
			frappe.db.get_value("LYQD Company", company, "books_company") or company
		)
		company_ccy = get_lyqd_company_currency(company)
		if frappe.db.exists("Company", books_company):
			company_ccy = (
				frappe.db.get_value("Company", books_company, "default_currency")
				or company_ccy
			).upper()
		amt = invoice_outstanding_in_company_currency(inv, company_ccy, as_of=as_of)
		# Split / Payment Schedule plan rows all share this voucher outstanding.
		# Per-row base_outstanding is not used — sync allocates across the family.
		return {
			"ok": True,
			"grain": "voucher",
			"amount": amt,
			"cleared": amt <= 0.01,
			"due_date": inv.due_date,
			"source_row": source_row,
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


def _source_family_rows(
	company: str,
	source_doctype: str,
	source_name: str,
) -> list[Any]:
	"""Planned/Paid plan rows that share the same books source."""
	return frappe.get_all(
		"LYQD Upcoming Payment",
		filters={
			"company": company,
			"source_doctype": source_doctype,
			"source_name": source_name,
			"status": ("in", ["Planned", "Paid"]),
		},
		fields=[
			"name",
			"title",
			"status",
			"amount",
			"due_date",
			"cash_effect",
			"source_row",
			"parent_payment",
			"balance_as_of",
		],
		order_by="due_date asc, name asc",
	)


def _is_account_split_family(family: list[Any]) -> bool:
	"""Same Account source Split in LYQD (multi-row or lyqd-split-* provenance)."""
	if len(family) > 1:
		return True
	return bool(family) and _is_lyqd_split_row(getattr(family[0], "source_row", None))


def _split_replace_family(doc) -> list[Any]:
	"""Plan rows superseded by Split / Re-split (Planned + Paid on same books source)."""
	if not doc.source_doctype or not doc.source_name:
		return [
			frappe._dict(
				{
					"name": doc.name,
					"title": doc.title,
					"status": doc.status,
					"amount": doc.amount,
					"due_date": doc.due_date,
					"cash_effect": doc.cash_effect,
					"source_row": getattr(doc, "source_row", None),
				}
			)
		]
	family = _source_family_rows(doc.company, doc.source_doctype, doc.source_name)
	if not family:
		return [
			frappe._dict(
				{
					"name": doc.name,
					"title": doc.title,
					"status": doc.status,
					"amount": doc.amount,
					"due_date": doc.due_date,
					"cash_effect": doc.cash_effect,
					"source_row": getattr(doc, "source_row", None),
				}
			)
		]
	# Re-split when already a LYQD split / multi-row family; else only the clicked row
	if _is_account_split_family(family) or any(
		_is_lyqd_split_row(getattr(r, "source_row", None)) for r in family
	):
		return family
	if doc.source_doctype in ("Purchase Invoice", "Sales Invoice") and len(family) > 1:
		return family
	# First split of a single books row — replace only this doc (not other unrelated)
	return [r for r in family if r.name == doc.name] or family[:1]


def _split_basis_amount(doc, family: list[Any]) -> tuple[float, str]:
	"""Amount new split rows must total — group net for nested Account roots."""
	return _group_net_basis(doc, family)


def _root_has_splits(name: str | None) -> bool:
	if not name:
		return False
	if frappe.db.exists("DocType", "LYQD Upcoming Split") and frappe.db.exists(
		"LYQD Upcoming Split", {"parent": name}
	):
		return True
	return False


def _assert_can_unlink_from_parent(child_name: str, parent_name: str | None) -> None:
	"""Block separating a nested child while the root still has a split schedule."""
	if not parent_name or not _root_has_splits(parent_name):
		return
	frappe.throw(
		frappe._(
			"Cannot unlink {0} while {1} has a split schedule. Merge or Re-split the parent first."
		).format(child_name, parent_name)
	)


def _delete_superseded_split_rows(
	company: str,
	names: list[str],
	*,
	source_doctype: str | None = None,
	source_name: str | None = None,
) -> list[str]:
	"""Hard-delete replaced plan rows + leftover Cancelled lyqd-split clutter for the source."""
	deleted: list[str] = []
	to_delete = set(names)
	if source_doctype and source_name:
		stale = frappe.get_all(
			"LYQD Upcoming Payment",
			filters={
				"company": company,
				"source_doctype": source_doctype,
				"source_name": source_name,
				"status": "Cancelled",
				"source_row": ("like", f"{LYQD_SPLIT_PREFIX}%"),
			},
			pluck="name",
		)
		to_delete.update(stale)
		# Also remove cancelled unsplitted original for this account/voucher
		stale_blank = frappe.get_all(
			"LYQD Upcoming Payment",
			filters={
				"company": company,
				"source_doctype": source_doctype,
				"source_name": source_name,
				"status": "Cancelled",
				"source_row": ("in", ["", None]),
			},
			pluck="name",
		)
		to_delete.update(stale_blank)

	for nm in list(to_delete):
		if not nm or not frappe.db.exists("LYQD Upcoming Payment", nm):
			continue
		try:
			frappe.delete_doc(
				"LYQD Upcoming Payment", nm, ignore_permissions=True, force=True
			)
			deleted.append(nm)
		except Exception:
			frappe.db.set_value("LYQD Upcoming Payment", nm, "status", "Cancelled")
	return deleted


def _is_books_split_source(doc) -> bool:
	"""Split / Re-split is for books-linked plan rows only (not manual Add payment)."""
	dt = (getattr(doc, "source_doctype", None) or "").strip()
	nm = (getattr(doc, "source_name", None) or "").strip()
	return bool(dt and nm and dt in ("Account", "Sales Invoice", "Purchase Invoice"))


def preview_split_upcoming_payment(name: str) -> dict[str, Any]:
	"""Suggested Split / Re-split rows (family, Payment Schedule, or current row)."""
	doc = frappe.get_doc("LYQD Upcoming Payment", name)
	frappe.only_for(("System Manager", "LYQD Manager", "LYQD User"))
	if doc.status not in ("Planned", "Paid"):
		frappe.throw(frappe._("Only Planned or Paid payments can be split"))
	if not _is_books_split_source(doc):
		frappe.throw(frappe._("Only books-linked plan rows can be split"))

	family = _split_replace_family(doc)
	basis, basis_source = _split_basis_amount(doc, family)
	table_splits = list(doc.get("splits") or [])
	resplit = bool(table_splits) or len(family) > 1 or any(
		_is_lyqd_split_row(getattr(r, "source_row", None)) for r in family
	)

	rows: list[dict[str, Any]] = []
	source = "current"

	# GL schedule table on this doc (preferred)
	if table_splits:
		rows = [
			{
				"due_date": str(r.due_date) if r.due_date else today(),
				"amount": flt(r.amount),
				"title": r.title or doc.title,
				"status": r.status or "Planned",
			}
			for r in table_splits
		]
		fam_total = sum(flt(r["amount"]) for r in rows)
		if basis > 0.01 and fam_total > 0.01 and abs(basis - fam_total) > 0.05:
			factor = basis / fam_total
			for r in rows:
				r["amount"] = flt(r["amount"] * factor, 2)
			drift = flt(basis - sum(flt(r["amount"]) for r in rows), 2)
			if rows and abs(drift) >= 0.01:
				rows[-1]["amount"] = flt(rows[-1]["amount"] + drift, 2)
		source = "existing_split"
	# Legacy multi-doc GL split → offer as remap rows (will consolidate to table on save)
	elif resplit and doc.source_doctype == "Account" and len(family) >= 1:
		rows = [
			{
				"due_date": str(r.due_date) if r.due_date else today(),
				"amount": flt(r.amount),
				"title": r.title,
				"status": r.status,
			}
			for r in family
		]
		fam_total = sum(flt(r["amount"]) for r in rows)
		if basis > 0.01 and fam_total > 0.01 and abs(basis - fam_total) > 0.05:
			factor = basis / fam_total
			for r in rows:
				r["amount"] = flt(r["amount"] * factor, 2)
			drift = flt(basis - sum(flt(r["amount"]) for r in rows), 2)
			if rows and abs(drift) >= 0.01:
				rows[-1]["amount"] = flt(rows[-1]["amount"] + drift, 2)
		source = "existing_split"
	elif resplit and len(family) >= 1 and doc.source_doctype != "Account":
		rows = [
			{
				"due_date": str(r.due_date) if r.due_date else today(),
				"amount": flt(r.amount),
				"title": r.title,
				"status": r.status,
			}
			for r in family
		]
		fam_total = sum(flt(r["amount"]) for r in rows)
		if basis > 0.01 and fam_total > 0.01 and abs(basis - fam_total) > 0.05:
			factor = basis / fam_total
			for r in rows:
				r["amount"] = flt(r["amount"] * factor, 2)
			drift = flt(basis - sum(flt(r["amount"]) for r in rows), 2)
			if rows and abs(drift) >= 0.01:
				rows[-1]["amount"] = flt(rows[-1]["amount"] + drift, 2)
		source = "existing_split"

	if source != "existing_split" and doc.source_doctype in (
		"Purchase Invoice",
		"Sales Invoice",
	) and doc.source_name:
		parts = _payment_schedule_seed_rows(
			doc.source_doctype,
			doc.source_name,
			basis=basis,
			title=doc.title,
			lyqd_company=doc.company,
			due_date=str(doc.due_date) if doc.due_date else None,
		)
		if parts:
			rows = parts
			source = "payment_schedule"

	if len(rows) < 1:
		rows = [
			{
				"due_date": str(doc.due_date) if doc.due_date else today(),
				"amount": basis,
				"title": doc.title,
			}
		]
		source = "current"

	return {
		"name": doc.name,
		"title": doc.title,
		"amount": flt(basis),
		"basis_source": basis_source,
		"cash_effect": doc.cash_effect,
		"source_doctype": doc.source_doctype,
		"source_name": doc.source_name,
		"preview_source": source,
		"resplit": resplit,
		"schedule": True,
		"family_names": [r.name for r in family],
		"family_size": max(len(family), len(table_splits) or 1),
		"rows": rows,
	}


def _parse_split_rows(rows: list[dict[str, Any]], *, default_title: str) -> list[dict[str, Any]]:
	base = _strip_split_index_suffix(default_title) or (default_title or "Split").strip()
	parsed: list[dict[str, Any]] = []
	for i, raw in enumerate(rows, start=1):
		due = raw.get("due_date")
		amt = flt(raw.get("amount"))
		if not due:
			frappe.throw(frappe._("Row {0}: due date is required").format(i))
		if amt <= 0.01:
			frappe.throw(frappe._("Row {0}: amount must be greater than zero").format(i))
		title = _strip_split_index_suffix(raw.get("title")) or base
		title = (title or "Split").strip()[:140]
		status = (raw.get("status") or "Planned").strip()
		if status not in ("Planned", "Paid"):
			status = "Planned"
		parsed.append(
			{
				"due_date": str(getdate(due)),
				"amount": amt,
				"title": title,
				"status": status,
			}
		)
	return parsed


def _use_gl_split_table(doc) -> bool:
	"""Account / PI / SI ladders use a child table on one Upcoming Payment (not N docs)."""
	if doc.get("splits"):
		return True
	if doc.source_doctype in ("Account", "Purchase Invoice", "Sales Invoice"):
		return True
	return False


def apply_gl_split_schedule(
	name: str,
	rows: list[dict[str, Any]],
	*,
	basis: float | None = None,
	basis_source: str = "plan_family",
) -> dict[str, Any]:
	"""Write the GL maturity/repayment ladder onto one Upcoming Payment.splits table."""
	doc = frappe.get_doc("LYQD Upcoming Payment", name)
	family = _split_replace_family(doc)
	if basis is None:
		basis, basis_source = _split_basis_amount(doc, family)

	parsed = _parse_split_rows(rows, default_title=doc.title)
	total = sum(p["amount"] for p in parsed)
	if abs(total - flt(basis)) > 0.05:
		frappe.throw(
			frappe._("Split amounts ({0}) must equal the {1} total ({2})").format(
				flt(total, 2),
				"books" if basis_source == "books" else "plan",
				flt(basis, 2),
			)
		)

	# Keep the canonical doc; delete sibling legacy multi-doc / lyqd-split-* rows
	keep = doc.name
	to_remove = [r.name for r in family if r.name != keep]
	# Legacy sibling (lyqd-split-* or Payment Schedule source_row): prefer oldest blank-row doc
	if getattr(doc, "source_row", None) and doc.source_doctype and doc.source_name:
		anchor = frappe.db.get_value(
			"LYQD Upcoming Payment",
			{
				"company": doc.company,
				"source_doctype": doc.source_doctype,
				"source_name": doc.source_name,
				"status": ("in", ["Planned", "Paid"]),
				"source_row": ("in", ["", None]),
			},
			"name",
			order_by="creation asc",
		)
		if not anchor:
			# All siblings have source_row — keep earliest in the family
			ordered = sorted(family, key=lambda r: str(getattr(r, "creation", None) or r.name))
			anchor = ordered[0].name if ordered else keep
		if anchor != keep:
			to_remove = [r.name for r in family if r.name != anchor]
			keep = anchor
			doc = frappe.get_doc("LYQD Upcoming Payment", keep)

	doc.source_row = None
	# Keep header title clean (no · 1/3 markers); installment index is UI-only
	clean_title = _strip_split_index_suffix(doc.title) or doc.title
	if clean_title and clean_title != doc.title:
		doc.title = clean_title[:140]
	# Preserve installment probabilities across re-split when due+amount match.
	prev_prob: dict[tuple[str, float], float] = {}
	for s in doc.get("splits") or []:
		key = (str(s.due_date or ""), flt(s.amount, 2))
		if s.probability is not None and s.probability != "":
			prev_prob[key] = flt(s.probability)
	header_prob = 100.0
	if (doc.cash_effect or "Outflow") in ("Inflow", "Setoff"):
		header_prob = (
			flt(doc.probability)
			if doc.probability is not None and doc.probability != ""
			else 100.0
		)
	doc.set("splits", [])
	if len(parsed) >= 2:
		for part in parsed:
			key = (str(part["due_date"] or ""), flt(part["amount"], 2))
			doc.append(
				"splits",
				{
					"due_date": part["due_date"],
					"amount": part["amount"],
					"title": part["title"],
					"status": part["status"],
					"probability": prev_prob.get(key, header_prob),
				},
			)
		# Splitting a GL balance freezes the ladder as of today (like Freeze as-of)
		doc.balance_as_of = today()
	# len == 1 → merge: empty splits table, header holds the single amount/due
	if len(parsed) == 1:
		doc.amount = parsed[0]["amount"]
		doc.due_date = parsed[0]["due_date"]
		doc.title = _strip_split_index_suffix(parsed[0]["title"]) or clean_title or doc.title
		doc.status = parsed[0]["status"]
		doc.balance_as_of = None
	doc.last_synced_on = frappe.utils.now_datetime() if doc.source_doctype else doc.last_synced_on
	doc.save(ignore_permissions=True)

	deleted = _delete_superseded_split_rows(
		doc.company,
		to_remove,
		source_doctype=doc.source_doctype,
		source_name=doc.source_name,
	)
	# Never delete the keeper
	if keep in deleted:
		deleted = [d for d in deleted if d != keep]

	return {
		"name": doc.name,
		"deleted": deleted,
		"created": [doc.as_dict()],
		"count": len(parsed),
		"basis": flt(basis),
		"basis_source": basis_source,
		"merged": len(parsed) < 2,
		"schedule": True,
		"splits": [
			{
				"due_date": s.due_date,
				"amount": flt(s.amount),
				"title": s.title,
				"status": s.status,
				"probability": flt(s.probability) if s.probability is not None else header_prob,
			}
			for s in (doc.get("splits") or [])
		],
	}


def split_upcoming_payment(name: str, rows: list[dict[str, Any]] | str | None = None) -> dict[str, Any]:
	"""Split a plan row into the ``splits`` child table on one Upcoming Payment.

	Account / PI / SI all use the schedule table. Payment Schedule (if any) is
	preview-only — never creates N docs or ``source_row`` keys.
	"""
	import json

	frappe.only_for(("System Manager", "LYQD Manager", "LYQD User"))
	if isinstance(rows, str):
		rows = json.loads(rows)
	rows = list(rows or [])
	if len(rows) < 1:
		frappe.throw(frappe._("Add at least one row"))

	doc = frappe.get_doc("LYQD Upcoming Payment", name)
	if doc.status not in ("Planned", "Paid"):
		frappe.throw(frappe._("Only Planned or Paid payments can be split"))
	if not _is_books_split_source(doc):
		frappe.throw(frappe._("Only books-linked plan rows can be split"))
	if int(getattr(doc, "is_recurring", 0) or 0):
		frappe.throw(frappe._("Recurring payments cannot be split — edit the series instead"))
	if getattr(doc, "parent_payment", None):
		frappe.throw(
			frappe._("Nested GL rows follow the parent due date — split the parent, or unlink first")
		)

	family = _split_replace_family(doc)
	basis, basis_source = _split_basis_amount(doc, family)
	return apply_gl_split_schedule(name, rows, basis=basis, basis_source=basis_source)


def mark_upcoming_split_paid(parent: str, split_row_name: str) -> dict[str, Any]:
	"""Mark one GL schedule line Paid (cash event; books may still show the balance)."""
	frappe.only_for(("System Manager", "LYQD Manager", "LYQD User"))
	doc = frappe.get_doc("LYQD Upcoming Payment", parent)
	found = False
	for row in doc.get("splits") or []:
		if row.name == split_row_name:
			row.status = "Paid"
			found = True
			break
	if not found:
		frappe.throw(frappe._("Split line not found"))
	doc.save(ignore_permissions=True)
	return doc.as_dict()


def _allocate_voucher_family_outstanding(
	planned: list[Any],
	outstanding: float,
) -> list[dict[str, Any]]:
	"""Apply voucher outstanding to Planned siblings — earliest due first. Keep due dates."""
	results: list[dict[str, Any]] = []
	outstanding = max(flt(outstanding), 0.0)
	planned_sorted = sorted(
		planned,
		key=lambda r: (str(r.due_date or "9999-99-99"), r.name),
	)

	if outstanding <= 0.01:
		for row in planned_sorted:
			doc = frappe.get_doc("LYQD Upcoming Payment", row.name)
			prev_amount = flt(doc.amount)
			prev_status = doc.status
			if doc.status != "Paid":
				doc.status = "Paid"
				doc.last_synced_on = frappe.utils.now_datetime()
				doc.save(ignore_permissions=True)
				action = "marked_paid"
			else:
				doc.last_synced_on = frappe.utils.now_datetime()
				doc.save(ignore_permissions=True)
				action = "unchanged"
			results.append(
				{
					"name": doc.name,
					"title": doc.title,
					"action": action,
					"status": doc.status,
					"amount": flt(doc.amount),
					"previous_amount": prev_amount,
					"previous_status": prev_status,
				}
			)
		return results

	total = sum(flt(r.amount) for r in planned_sorted)
	if abs(total - outstanding) <= 0.01:
		for row in planned_sorted:
			doc = frappe.get_doc("LYQD Upcoming Payment", row.name)
			doc.last_synced_on = frappe.utils.now_datetime()
			doc.save(ignore_permissions=True)
			results.append(
				{
					"name": doc.name,
					"title": doc.title,
					"action": "unchanged",
					"status": doc.status,
					"amount": flt(doc.amount),
					"previous_amount": flt(doc.amount),
					"previous_status": doc.status,
				}
			)
		return results

	if outstanding < total - 0.01:
		need_cut = flt(total - outstanding, 2)
		for row in planned_sorted:
			doc = frappe.get_doc("LYQD Upcoming Payment", row.name)
			prev_amount = flt(doc.amount)
			prev_status = doc.status
			action = "unchanged"
			if need_cut > 0.01:
				cut = min(prev_amount, need_cut)
				need_cut = flt(need_cut - cut, 2)
				new_amt = flt(prev_amount - cut, 2)
				if new_amt <= 0.01:
					doc.status = "Paid"
					# Keep prior installment amount for history
					action = "marked_paid"
				else:
					doc.amount = new_amt
					action = "amount_updated"
			doc.last_synced_on = frappe.utils.now_datetime()
			doc.save(ignore_permissions=True)
			results.append(
				{
					"name": doc.name,
					"title": doc.title,
					"action": action,
					"status": doc.status,
					"amount": flt(doc.amount),
					"previous_amount": prev_amount,
					"previous_status": prev_status,
				}
			)
		return results

	# Outstanding grew — put the increase on the latest open row
	extra = flt(outstanding - total, 2)
	for i, row in enumerate(planned_sorted):
		doc = frappe.get_doc("LYQD Upcoming Payment", row.name)
		prev_amount = flt(doc.amount)
		prev_status = doc.status
		action = "unchanged"
		if i == len(planned_sorted) - 1 and extra > 0.01:
			doc.amount = flt(prev_amount + extra, 2)
			action = "amount_updated"
		doc.last_synced_on = frappe.utils.now_datetime()
		doc.save(ignore_permissions=True)
		results.append(
			{
				"name": doc.name,
				"title": doc.title,
				"action": action,
				"status": doc.status,
				"amount": flt(doc.amount),
				"previous_amount": prev_amount,
				"previous_status": prev_status,
			}
		)
	return results


def sync_voucher_family_from_books(
	company: str,
	source_doctype: str,
	source_name: str,
	*,
	trigger_name: str | None = None,
) -> dict[str, Any]:
	"""Refresh all plan rows for one PI/SI using voucher outstanding (no schedule base_outstanding)."""
	family = _source_family_rows(company, source_doctype, source_name)
	if not family:
		return {
			"name": trigger_name,
			"action": "skipped",
			"reason": "no_family",
			"grain": "voucher",
			"family": [],
		}

	sample = family[0]
	live = resolve_books_outstanding(
		company,
		source_doctype,
		source_name,
		account=frappe.db.get_value("LYQD Upcoming Payment", sample.name, "source_account"),
		as_of=None,
		source_row=None,
	)
	if not live.get("ok"):
		return {
			"name": trigger_name or sample.name,
			"action": "skipped",
			"reason": live.get("reason") or "no_source",
			"grain": "voucher",
			"family": [r.name for r in family],
		}

	if live.get("cancelled") or live.get("missing"):
		results = []
		for row in family:
			if row.status == "Cancelled":
				continue
			doc = frappe.get_doc("LYQD Upcoming Payment", row.name)
			prev = doc.status
			doc.status = "Cancelled"
			doc.amount = 0
			doc.last_synced_on = frappe.utils.now_datetime()
			doc.save(ignore_permissions=True)
			results.append(
				{
					"name": doc.name,
					"title": doc.title,
					"action": "cancelled",
					"status": doc.status,
					"previous_status": prev,
				}
			)
		return {
			"name": trigger_name or sample.name,
			"title": sample.title,
			"action": "cancelled",
			"grain": "voucher",
			"live_amount": 0.0,
			"plan_total": 0.0,
			"family": results,
			"family_size": len(family),
		}

	planned = [r for r in family if r.status == "Planned"]
	# Touch Paid rows' last_synced
	for row in family:
		if row.status == "Paid":
			frappe.db.set_value(
				"LYQD Upcoming Payment",
				row.name,
				"last_synced_on",
				frappe.utils.now_datetime(),
				update_modified=False,
			)

	if not planned:
		return {
			"name": trigger_name or sample.name,
			"title": sample.title,
			"action": "unchanged",
			"grain": "voucher",
			"live_amount": flt(live.get("amount")),
			"plan_total": 0.0,
			"family": [],
			"family_size": len(family),
			"status": "Paid",
		}

	# Reopen if books have outstanding but everything was Paid — put on earliest paid
	# (only when no Planned left — handled above). If all Paid and OS > 0:
	if not planned and flt(live.get("amount")) > 0.01:
		# reopen earliest Paid into Planned with full OS on that one row — rare
		pass

	member_results = _allocate_voucher_family_outstanding(planned, flt(live.get("amount")))
	actions = {r["action"] for r in member_results}
	if "marked_paid" in actions and len(actions) == 1:
		action = "marked_paid"
	elif "amount_updated" in actions or "marked_paid" in actions:
		action = "amount_updated" if "amount_updated" in actions else "marked_paid"
		if "marked_paid" in actions and "amount_updated" in actions:
			action = "amount_updated"
	elif "cancelled" in actions:
		action = "cancelled"
	else:
		action = "unchanged"

	plan_total = sum(
		flt(r["amount"])
		for r in member_results
		if r.get("status") == "Planned"
	)
	return {
		"name": trigger_name or sample.name,
		"title": sample.title,
		"action": action,
		"grain": "voucher",
		"live_amount": flt(live.get("amount")),
		"plan_total": plan_total,
		"difference": flt(live.get("amount")) - plan_total,
		"family": member_results,
		"family_size": len(family),
		"cash_effect": frappe.db.get_value(
			"LYQD Upcoming Payment", sample.name, "cash_effect"
		)
		or "Outflow",
		"status": member_results[0]["status"] if member_results else sample.status,
		"amount": plan_total,
		"as_of_used": str(getdate(today())),
	}


def sync_account_schedule_from_books(name: str, as_of: str | None = None) -> dict[str, Any]:
	"""One plan row with ``splits`` table: compare live books (group net for nests) vs schedule.

	Writing a split freezes the ladder (``balance_as_of``). Refresh never rewrites
	dates/amounts; if live books moved, SPA prompts to Adjust split or keep.
	"""
	_ = as_of  # schedule always compares live today / group net
	doc = frappe.get_doc("LYQD Upcoming Payment", name)
	basis, basis_source = _group_net_basis(doc)
	if basis_source in ("row", "plan_family", "plan_group") and not doc.source_name:
		return {"name": name, "action": "skipped", "reason": "no_source", "grain": "account"}

	# Prefer live books; if books unavailable basis falls back to plan — still compare
	books_amount = flt(basis)
	try:
		if doc.source_doctype == "Account" and doc.source_name:
			live_single = resolve_books_outstanding(
				doc.company,
				"Account",
				doc.source_name,
				account=doc.source_name,
				as_of=None,
			)
			if not live_single.get("ok") and basis_source.startswith("plan"):
				return {
					"name": name,
					"action": "skipped",
					"reason": live_single.get("reason") or "no_source",
					"grain": "account",
				}
		elif doc.source_doctype in ("Purchase Invoice", "Sales Invoice") and doc.source_name:
			live_single = resolve_books_outstanding(
				doc.company,
				doc.source_doctype,
				doc.source_name,
				account=getattr(doc, "source_account", None),
				as_of=None,
			)
			if not live_single.get("ok") and basis_source.startswith("plan"):
				return {
					"name": name,
					"action": "skipped",
					"reason": live_single.get("reason") or "no_source",
					"grain": "voucher",
				}
			if live_single.get("ok"):
				books_amount = max(flt(live_single.get("amount")), 0.0)
	except Exception:
		frappe.log_error(title="LYQD schedule refresh")
		return {"name": name, "action": "skipped", "reason": "books_error", "grain": "account"}

	# Nested Account root: books_amount already = group net from _group_net_basis
	if doc.source_doctype == "Account" and basis_source in ("books_group", "books"):
		books_amount = flt(basis)

	splits = list(doc.get("splits") or [])
	planned = [r for r in splits if (r.status or "Planned") == "Planned"]
	paid = [r for r in splits if (r.status or "") == "Paid"]
	plan_total = sum(flt(r.amount) for r in planned)
	paid_on_plan = sum(flt(r.amount) for r in paid)
	covered = flt(plan_total + paid_on_plan, 2)
	unexplained = flt(books_amount - covered, 2)

	doc.last_synced_on = frappe.utils.now_datetime()
	# Ensure split ladders stay frozen (legacy rows may lack balance_as_of)
	if splits and not getattr(doc, "balance_as_of", None):
		doc.balance_as_of = today()
	doc.save(ignore_permissions=True)

	suggest_adjust_split = abs(unexplained) > 0.01
	if not suggest_adjust_split:
		action = "awaiting_books" if paid_on_plan > 0.01 else "unchanged"
	else:
		action = "reconcile"

	grain = "voucher" if doc.source_doctype in ("Purchase Invoice", "Sales Invoice") else "account"
	return {
		"name": name,
		"title": doc.title,
		"action": action,
		"grain": grain,
		"split_family": True,
		"schedule": True,
		"suggest_adjust_split": suggest_adjust_split,
		"live_amount": books_amount,
		"books_amount": books_amount,
		"basis_source": basis_source,
		"plan_total": plan_total,
		"paid_on_plan": paid_on_plan,
		"covered_total": covered,
		"difference": unexplained,
		"family_size": len(splits),
		"cash_effect": doc.cash_effect or "Outflow",
		"status": doc.status,
		"amount": covered,
		"balance_as_of": str(doc.balance_as_of) if doc.balance_as_of else None,
		"as_of_used": str(getdate(today())),
		"suggest_unfreeze": False,
		"live_today_amount": books_amount if suggest_adjust_split else None,
	}


def sync_account_split_family_from_books(
	company: str,
	source_name: str,
	*,
	trigger_name: str | None = None,
	as_of: str | None = None,
) -> dict[str, Any]:
	"""Legacy multi-doc GL Split family: compare live books vs plan — never rewrite ladder amounts.

	Paid-on-plan rows are treated as *awaiting books* (cash moved, GL not yet posted).
	Unexplained gap = books − (Planned + Paid). Near-zero means the ladder still matches
	GL even if some maturities were marked Paid early.
	"""
	family = _source_family_rows(company, "Account", source_name)
	if not family:
		return {
			"name": trigger_name,
			"action": "skipped",
			"reason": "no_family",
			"grain": "account",
		}

	sample = next((r for r in family if r.name == trigger_name), family[0])
	sync_as_of = as_of or sample.balance_as_of or None
	live = resolve_books_outstanding(
		company,
		"Account",
		source_name,
		account=source_name,
		as_of=sync_as_of,
	)
	if not live.get("ok"):
		return {
			"name": trigger_name or sample.name,
			"action": "skipped",
			"reason": live.get("reason") or "no_source",
			"grain": "account",
		}

	books_amount = max(flt(live.get("amount")), 0.0)
	planned = [r for r in family if r.status == "Planned"]
	paid = [r for r in family if r.status == "Paid"]
	plan_total = sum(flt(r.amount) for r in planned)
	paid_on_plan = sum(flt(r.amount) for r in paid)
	covered = flt(plan_total + paid_on_plan, 2)
	# Unexplained movement in GL vs the full ladder (including Paid awaiting books)
	unexplained = flt(books_amount - covered, 2)

	now = frappe.utils.now_datetime()
	for row in family:
		frappe.db.set_value(
			"LYQD Upcoming Payment",
			row.name,
			"last_synced_on",
			now,
			update_modified=False,
		)

	if abs(unexplained) <= 0.01:
		action = "awaiting_books" if paid_on_plan > 0.01 else "unchanged"
	else:
		action = "reconcile"

	return {
		"name": trigger_name or sample.name,
		"title": sample.title,
		"action": action,
		"grain": "account",
		"split_family": True,
		"live_amount": books_amount,
		"books_amount": books_amount,
		"plan_total": plan_total,
		"paid_on_plan": paid_on_plan,
		"covered_total": covered,
		"difference": unexplained,
		"family_size": len(family),
		"family": [
			{"name": r.name, "amount": flt(r.amount), "status": r.status} for r in family
		],
		"cash_effect": live.get("cash_effect")
		or frappe.db.get_value("LYQD Upcoming Payment", sample.name, "cash_effect")
		or "Outflow",
		"status": sample.status,
		"amount": plan_total,
		"balance_as_of": str(sample.balance_as_of) if sample.balance_as_of else None,
		"as_of_used": str(getdate(sync_as_of)) if sync_as_of else str(getdate(today())),
		"suggest_unfreeze": False,
		"live_today_amount": None,
	}


def _consolidate_legacy_split_family(name: str) -> str | None:
	"""Fold multi-doc SI/PI/Account lyqd-split-* families into one splits table.

	Returns the keeper name, or None if nothing to consolidate.
	"""
	doc = frappe.get_doc("LYQD Upcoming Payment", name)
	if not doc.source_doctype or not doc.source_name:
		return None
	if doc.get("splits") or frappe.db.exists("LYQD Upcoming Split", {"parent": doc.name}):
		return doc.name

	family = _source_family_rows(doc.company, doc.source_doctype, doc.source_name)
	needs = len(family) > 1 or any(
		_is_lyqd_split_row(getattr(r, "source_row", None))
		or (getattr(r, "source_row", None) or "")
		for r in family
	)
	# Payment Schedule child names also count as legacy multi-doc installments
	if not needs:
		return None
	if len(family) <= 1 and not (getattr(doc, "source_row", None) or ""):
		return None

	rows = [
		{
			"due_date": str(r.due_date) if r.due_date else today(),
			"amount": flt(r.amount),
			"title": r.title or doc.title,
			"status": r.status if r.status in ("Planned", "Paid") else "Planned",
		}
		for r in sorted(family, key=lambda x: (str(x.due_date or "9999"), x.name))
		if flt(r.amount) > 0.01
	]
	if len(rows) < 2:
		# Single leftover with a source_row key — clear key onto one doc
		doc.source_row = None
		doc.save(ignore_permissions=True)
		return doc.name

	basis = sum(flt(r["amount"]) for r in rows)
	out = apply_gl_split_schedule(
		doc.name, rows, basis=basis, basis_source="plan_family"
	)
	return out.get("name") or doc.name


def sync_upcoming_payment_from_books(name: str, as_of: str | None = None) -> dict[str, Any]:
	"""Refresh one Planned (or reopenable) Upcoming Payment from ERPNext books.

	- Schedule table (Account / SI / PI): compare live books vs ladder.
	- Legacy multi-doc SI/PI splits: consolidate onto one schedule, then compare.
	- Single Account-grain: refresh GL amount (freeze date honored).
	"""
	doc = frappe.get_doc("LYQD Upcoming Payment", name)
	if not is_erpnext_integration_enabled(doc.company):
		frappe.throw(frappe._("Enable ERPNext integration to sync from books"))

	# Ignored stays ignored until the user restores via Add to plan / status edit
	if doc.status == "Ignored":
		return {"name": name, "action": "skipped", "reason": "ignored"}

	if doc.status not in ("Planned", "Paid"):
		return {"name": name, "action": "skipped", "reason": "status"}

	if not doc.source_doctype or not doc.source_name:
		return {"name": name, "action": "skipped", "reason": "manual_row"}

	# Child-table schedule (Account nest root, SI/PI, or legacy GL)
	if doc.get("splits") or frappe.db.exists(
		"LYQD Upcoming Split", {"parent": doc.name}
	):
		return sync_account_schedule_from_books(doc.name, as_of=as_of)

	# Legacy multi-doc voucher / Account splits → one schedule table
	if doc.source_doctype in ("Purchase Invoice", "Sales Invoice", "Account"):
		kept = _consolidate_legacy_split_family(doc.name)
		if kept and (
			frappe.db.exists("LYQD Upcoming Split", {"parent": kept})
			or frappe.get_doc("LYQD Upcoming Payment", kept).get("splits")
		):
			return sync_account_schedule_from_books(kept, as_of=as_of)

	if doc.source_doctype in ("Purchase Invoice", "Sales Invoice"):
		return sync_voucher_family_from_books(
			doc.company,
			doc.source_doctype,
			doc.source_name,
			trigger_name=name,
		)

	if doc.source_doctype == "Account":
		family = _source_family_rows(doc.company, "Account", doc.source_name)
		if _is_account_split_family(family):
			return sync_account_split_family_from_books(
				doc.company,
				doc.source_name,
				trigger_name=name,
				as_of=as_of,
			)

	sync_as_of = as_of or getattr(doc, "balance_as_of", None) or None
	live = resolve_books_outstanding(
		doc.company,
		doc.source_doctype,
		doc.source_name,
		account=getattr(doc, "source_account", None),
		as_of=sync_as_of,
		source_row=getattr(doc, "source_row", None),
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
		# Single GL balance grain (e.g. TDS / GST): keep Planned; update amount.
		new_amt = max(flt(live.get("amount")), 0.0)
		new_ce = live.get("cash_effect")
		if new_ce == "Setoff":
			new_ce = "Inflow"
		ce_changed = new_ce in ("Outflow", "Inflow") and doc.cash_effect != new_ce
		if ce_changed:
			doc.cash_effect = new_ce
		if live.get("title") and live.get("signed_net") is not None:
			doc.title = str(live["title"])[:140]
		if doc.status != "Planned":
			doc.status = "Planned"
			doc.amount = new_amt
			action = "reopened" if prev_status != "Planned" else "amount_updated"
		elif abs(new_amt - prev_amount) > 0.01 or ce_changed:
			doc.amount = new_amt
			action = "amount_updated"
	elif live.get("cleared"):
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

		# Single non-split voucher path (should be rare — families handled above)
		if live.get("due_date") and not doc.due_date:
			doc.due_date = live["due_date"]

	doc.last_synced_on = frappe.utils.now_datetime()
	doc.save(ignore_permissions=True)

	suggest_unfreeze = False
	live_today_amount = None
	if (
		grain == "account"
		and getattr(doc, "balance_as_of", None)
		and doc.status == "Planned"
	):
		live_today = resolve_books_outstanding(
			doc.company,
			doc.source_doctype,
			doc.source_name,
			account=getattr(doc, "source_account", None),
			as_of=None,
		)
		if live_today.get("ok") and not live_today.get("cancelled") and not live_today.get("missing"):
			live_today_amount = max(flt(live_today.get("amount")), 0.0)
			if live_today_amount < flt(doc.amount) - 0.01:
				suggest_unfreeze = True

	return {
		"name": name,
		"title": doc.title,
		"action": action,
		"status": doc.status,
		"amount": flt(doc.amount),
		"previous_amount": prev_amount,
		"previous_status": prev_status,
		"live_amount": flt(live.get("amount")),
		"grain": grain,
		"cash_effect": doc.cash_effect or "Outflow",
		"parent_payment": doc.parent_payment,
		"balance_as_of": str(doc.balance_as_of) if getattr(doc, "balance_as_of", None) else None,
		"as_of_used": str(getdate(sync_as_of)) if sync_as_of else str(getdate(today())),
		"suggest_unfreeze": suggest_unfreeze,
		"live_today_amount": live_today_amount,
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

	# Split schedule owns the freeze — cannot Unfreeze while ladder exists
	if as_of is None and (
		doc.get("splits")
		or frappe.db.exists("LYQD Upcoming Split", {"parent": name})
	):
		frappe.throw(
			frappe._(
				"This plan has a split schedule. Use Re-split / Adjust split "
				"(or Merge) instead of Unfreeze."
			)
		)

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

	# Unfreeze + GL schedule: if live books ≠ ladder, SPA should prompt Adjust split
	suggest_adjust_split = False
	adjust_payload = None
	if as_of_s is None:
		primary = frappe.get_doc("LYQD Upcoming Payment", name)
		if primary.get("splits") or frappe.db.exists(
			"LYQD Upcoming Split", {"parent": name}
		):
			adj = sync_account_schedule_from_books(name)
			if adj.get("suggest_adjust_split"):
				suggest_adjust_split = True
				adjust_payload = adj

	return {
		"name": name,
		"balance_as_of": as_of_s,
		"updated": targets,
		"synced": results,
		"suggest_adjust_split": suggest_adjust_split,
		"split_adjust": adjust_payload,
	}


def sync_planned_from_books(company: str) -> dict[str, Any]:
	"""
	Sync all ERPNext-sourced Planned (and Paid-with-source) Upcoming Payments for a company.

	- PI/SI families: allocate voucher outstanding (earliest due first)
	- Account Split families: compare-only (Books vs Plan)
	- Single Account-grain: refresh GL as of balance_as_of (or today)
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
		fields=["name", "source_doctype", "source_name"],
	)
	results = []
	seen_families: set[tuple[str, str, str]] = set()
	for row in rows:
		if row.source_doctype in ("Purchase Invoice", "Sales Invoice"):
			fkey = ("voucher", row.source_doctype, row.source_name)
		elif row.source_doctype == "Account":
			family = _source_family_rows(company, "Account", row.source_name)
			if _is_account_split_family(family):
				fkey = ("account_split", "Account", row.source_name)
			else:
				fkey = ("row", row.name, "")
		else:
			fkey = ("row", row.name, "")
		if fkey in seen_families:
			continue
		seen_families.add(fkey)
		results.append(sync_upcoming_payment_from_books(row.name))

	nested = sync_nested_account_plans(company)

	# SPA: freeze-date vs live (GST) and split-schedule vs live (FD/loan ladders)
	freeze_compare = [
		r
		for r in results
		if r.get("live_today_amount") is not None
		and (r.get("balance_as_of") or r.get("suggest_adjust_split"))
	]
	summary = {
		"marked_paid": sum(1 for r in results if r.get("action") == "marked_paid"),
		"amount_updated": sum(1 for r in results if r.get("action") == "amount_updated"),
		"cancelled": sum(1 for r in results if r.get("action") == "cancelled"),
		"reopened": sum(1 for r in results if r.get("action") == "reopened"),
		"unchanged": sum(1 for r in results if r.get("action") == "unchanged"),
		"reconcile": sum(1 for r in results if r.get("action") == "reconcile"),
		"awaiting_books": sum(1 for r in results if r.get("action") == "awaiting_books"),
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
		"freeze_compare": freeze_compare,
	}
