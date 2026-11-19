"""
Investable surplus calculator for LYQD.

investable_surplus =
  sum(eligible bank cash)
  − sum(Upcoming Payment where status=Planned and due_date ≤ today+horizon)
  − min_liquidity_buffer
  − restricted_cash

Overdue Planned payments (due_date < today) are included — still committed cash.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import frappe
from frappe.utils import add_days, cint, flt, getdate, today

from lyqd.cash.bank_cash import get_eligible_bank_cash


def parse_horizon_days(horizon_days: int | str | None, default: int = 7) -> int:
	"""Free-form forecast horizon in days (UI may suggest 7/14/30/60). Minimum 1."""
	try:
		n = int(horizon_days if horizon_days is not None else default)
	except (TypeError, ValueError):
		n = default
	return max(1, n)


def _cash_effect(row: dict[str, Any] | None) -> str:
	return (row or {}).get("cash_effect") or "Outflow"


def _is_nest_child(row: dict[str, Any] | None) -> bool:
	"""Account-nest child (not a GL schedule installment)."""
	if not row:
		return False
	if row.get("_schedule"):
		return False
	parent = row.get("parent_payment")
	return bool(parent)


def _signed_plan_amount(row: dict[str, Any] | None) -> float:
	"""Outflow +; Inflow/Setoff − — same as nest ``group_net``."""
	amt = flt((row or {}).get("amount"))
	if _cash_effect(row) in ("Inflow", "Setoff"):
		return -amt
	return amt


def nest_group_maps(
	payments: list[dict[str, Any]] | None,
) -> tuple[dict[str, list[dict[str, Any]]], set[str]]:
	"""Map nest root → children; set of nest-child names (exclude schedule lines)."""
	payments = payments or []
	by_name = {p.get("name"): p for p in payments if p.get("name")}
	children_of: dict[str, list[dict[str, Any]]] = {}
	child_names: set[str] = set()
	for p in payments:
		if not _is_nest_child(p):
			continue
		parent = p.get("parent_payment")
		if parent and parent in by_name and parent != p.get("name"):
			children_of.setdefault(parent, []).append(p)
			if p.get("name"):
				child_names.add(p["name"])
	return children_of, child_names


def plan_card_totals(payments: list[dict[str, Any]] | None) -> dict[str, float]:
	"""Commitments / incoming card totals with nested GL collapsed to ``group_net``.

	Nest children are not counted on their own. A nest root contributes its signed
	group net once (positive → commitments, negative → incoming). Plain roots and
	GL schedule installments keep their own cash_effect.
	"""
	payments = payments or []
	children_of, child_names = nest_group_maps(payments)
	commitments_total = 0.0
	incoming_total = 0.0
	incoming_expected = 0.0

	def _prob(row: dict[str, Any]) -> float:
		prob = row.get("probability")
		if prob is None or prob == "":
			prob = 100
		return min(max(flt(prob), 0), 100) / 100.0

	for p in payments:
		name = p.get("name")
		if name and name in child_names:
			continue
		if _is_nest_child(p):
			continue

		kids = children_of.get(name or "", []) or []
		if kids:
			# Net from rows in this Planned list only (Paid nest kids are already excluded)
			net = _signed_plan_amount(p) + sum(_signed_plan_amount(c) for c in kids)
			if net > 0.01:
				commitments_total += net
			elif net < -0.01:
				face = abs(net)
				incoming_total += face
				incoming_expected += face * _prob(p)
			continue

		effect = _cash_effect(p)
		amt = flt(p.get("amount"))
		if effect == "Outflow":
			commitments_total += amt
		elif effect in ("Inflow", "Setoff"):
			incoming_total += amt
			incoming_expected += amt * _prob(p)

	return {
		"commitments_total": flt(commitments_total),
		"incoming_total": flt(incoming_total),
		"incoming_expected": flt(incoming_expected),
		# Free-cash reserve matches Commitments (outflow-side nest nets + plain outflows)
		"upcoming_total": flt(commitments_total),
	}


@dataclass
class ExplanationLine:
	kind: str  # cash | upcoming | buffer | restricted | total
	label: str
	amount: float
	sign: str  # + or -
	ref_doctype: str | None = None
	ref_name: str | None = None
	due_date: str | None = None
	category: str | None = None
	notes: str | None = None
	# Grouped commitments: amount/sign are net; gl_* is this row's own books amount
	gl_amount: float | None = None
	gl_sign: str | None = None
	child_count: int = 0
	children: list[ExplanationLine] = field(default_factory=list)


@dataclass
class SurplusResult:
	company: str
	as_of: str
	horizon_days: int
	horizon_end: str
	bank_cash: float
	upcoming_total: float
	min_liquidity_buffer: float
	restricted_cash: float
	investable_surplus: float
	is_shortfall: bool
	explanation: list[ExplanationLine] = field(default_factory=list)
	cash_accounts: list[dict[str, Any]] = field(default_factory=list)
	upcoming_payments: list[dict[str, Any]] = field(default_factory=list)
	policy_name: str | None = None

	def as_dict(self) -> dict[str, Any]:
		data = asdict(self)
		return data


def get_policy(company: str) -> frappe._dict:
	"""Load Policy fields from LYQD Company, falling back to LYQD Settings defaults."""
	if company and frappe.db.exists("LYQD Company", company):
		row = frappe.db.get_value(
			"LYQD Company",
			company,
			[
				"name",
				"min_liquidity_buffer",
				"restricted_cash",
				"default_forecast_horizon_days",
			],
			as_dict=True,
		)
		if row:
			# Defaults when company exists but policy scalars were never set
			if row.default_forecast_horizon_days is None:
				settings = (
					frappe.get_single("LYQD Settings")
					if frappe.db.exists("DocType", "LYQD Settings")
					else None
				)
				row.min_liquidity_buffer = flt(
					row.min_liquidity_buffer
					if row.min_liquidity_buffer is not None
					else (settings.get("default_min_liquidity_buffer") if settings else 0)
				)
				row.restricted_cash = flt(
					row.restricted_cash
					if row.restricted_cash is not None
					else (settings.get("default_restricted_cash") if settings else 0)
				)
				row.default_forecast_horizon_days = int(
					(settings.get("default_forecast_horizon_days") if settings else None) or 7
				)
			return row

	settings = (
		frappe.get_single("LYQD Settings")
		if frappe.db.exists("DocType", "LYQD Settings")
		else None
	)
	return frappe._dict(
		{
			"name": None,
			"min_liquidity_buffer": flt(
				settings.get("default_min_liquidity_buffer") if settings else 0
			),
			"restricted_cash": flt(settings.get("default_restricted_cash") if settings else 0),
			"default_forecast_horizon_days": int(
				(settings.get("default_forecast_horizon_days") if settings else None) or 7
			),
		}
	)


def _is_credit_facility(account_type: str | None) -> bool:
	"""Cash Credit / Overdraft — drawn balances reduce free cash; unused limit does not."""
	from lyqd.cash.bank_cash import is_credit_facility

	return is_credit_facility(account_type)


def _bank_cash_explanation_label(row: dict[str, Any], *, drawn: bool) -> str:
	name = row.get("account_name") or row.get("bank_account") or "Bank account"
	acct_type = (row.get("account_type") or "").strip()
	if _is_credit_facility(acct_type):
		if drawn:
			return f"Bank cash — {name} (CC drawn)"
		return f"Bank cash — {name} ({acct_type})"
	if drawn:
		return f"Bank cash — {name} (drawn)"
	return f"Bank cash — {name}"


def get_planned_upcoming_payments(
	company: str,
	as_of: str,
	horizon_days: int,
) -> list[dict[str, Any]]:
	"""
	Committed forecast: Planned payments due on or before as_of+horizon.

	Includes overdue (due_date < as_of) — still Planned means cash is still committed.
	Excludes Paid / Cancelled.

	Recurring Outflow / Inflow series: one doc; ``amount`` is expanded to the sum
	of cycles that fall in the horizon (period amount kept as ``period_amount``).
	Only Outflow totals reserve free cash; Inflow totals feed expected incoming.
	"""
	from lyqd.cash.recurring import expand_recurring_row

	end = getdate(add_days(getdate(as_of), horizon_days))
	rows = frappe.get_all(
		"LYQD Upcoming Payment",
		filters={
			"company": company,
			"status": "Planned",
			"due_date": ["<=", end],
		},
		fields=[
			"name",
			"due_date",
			"amount",
			"cash_effect",
			"probability",
			"category",
			"status",
			"notes",
			"title",
			"source_doctype",
			"source_name",
			"source_account",
			"parent_payment",
			"group_net",
			"is_recurring",
			"frequency",
			"recurrence_end",
		],
		order_by="due_date asc, amount desc",
	)
	# GL / voucher split schedules (child table) — expand Planned lines by due date
	split_parents = [r.name for r in rows]
	splits_by_parent: dict[str, list] = {}
	# Nest children of any split root are detail-only (schedule owns group net)
	split_root_names: set[str] = set()
	if frappe.db.exists("DocType", "LYQD Upcoming Split"):
		parents_with_splits = frappe.get_all(
			"LYQD Upcoming Split",
			filters={"parenttype": "LYQD Upcoming Payment"},
			pluck="parent",
			distinct=True,
		)
		if parents_with_splits:
			split_root_names = set(
				frappe.get_all(
					"LYQD Upcoming Payment",
					filters={
						"company": company,
						"name": ("in", parents_with_splits),
						"status": ("in", ["Planned", "Paid"]),
					},
					pluck="name",
				)
			)
		if split_parents:
			for s in frappe.get_all(
				"LYQD Upcoming Split",
				filters={"parent": ("in", split_parents), "status": "Planned"},
				fields=["name", "parent", "due_date", "amount", "title", "status", "probability"],
				order_by="due_date asc, idx asc",
			):
				splits_by_parent.setdefault(s.parent, []).append(s)

	out: list[dict[str, Any]] = []
	for row in rows:
		parent = row.get("parent_payment")
		if parent and parent in split_root_names:
			continue
		expand_recurring_row(row, as_of, horizon_days)
		# Drop recurring series with nothing left in this horizon (e.g. past end)
		if cint(row.get("is_recurring")) and flt(row.get("amount")) <= 0.01:
			continue
		schedule = splits_by_parent.get(row.name) or []
		if schedule:
			for s in schedule:
				if getdate(s.due_date) > end:
					continue
				line = dict(row)
				# Unique identity so Cash position can mark one maturity Paid
				# (parent doc name alone is shared across the ladder).
				line["name"] = f"{row.name}::split::{s.name}"
				line["amount"] = flt(s.amount)
				line["due_date"] = s.due_date
				line["title"] = s.title or row.get("title")
				line["split_name"] = s.name
				line["split_row"] = s.name
				line["parent_payment"] = row.name
				line["_schedule"] = 1
				line["is_recurring"] = 0
				# Per-installment probability; fall back to parent header.
				if s.probability is not None and s.probability != "":
					line["probability"] = flt(s.probability)
				out.append(line)
			continue
		out.append(row)
	# Chronological across parents + expanded GL schedule lines (Cash position list)
	out.sort(
		key=lambda r: (
			str(r.get("due_date") or "9999-99-99"),
			-flt(r.get("amount")),
			str(r.get("name") or ""),
		)
	)
	return out


def compute_surplus(
	company: str,
	horizon_days: int | None = None,
	as_of: str | None = None,
	*,
	bank_cash: float | None = None,
	cash_accounts: list[dict[str, Any]] | None = None,
	upcoming_payments: list[dict[str, Any]] | None = None,
	min_liquidity_buffer: float | None = None,
	restricted_cash: float | None = None,
) -> SurplusResult:
	"""
	Compute investable surplus with a readable explanation.

	Pure overrides (bank_cash, cash_accounts, upcoming_payments, buffers) support
	unit tests without DocType fixtures. When omitted, values are loaded from the site.

	Drawn cash-credit / overdraft balances (negative) reduce bank cash. Unused CC
	limit is never included in free cash.
	"""
	as_of = str(getdate(as_of or today()))
	needs_policy = (
		horizon_days is None
		or min_liquidity_buffer is None
		or restricted_cash is None
	)
	policy = get_policy(company) if needs_policy else frappe._dict({"name": None})

	if horizon_days is None:
		horizon_days = policy.get("default_forecast_horizon_days") or 7
	horizon_days = parse_horizon_days(horizon_days)
	horizon_end = str(getdate(add_days(as_of, horizon_days)))

	if min_liquidity_buffer is None:
		min_liquidity_buffer = flt(policy.get("min_liquidity_buffer"))
	else:
		min_liquidity_buffer = flt(min_liquidity_buffer)

	if restricted_cash is None:
		restricted_cash = flt(policy.get("restricted_cash"))
	else:
		restricted_cash = flt(restricted_cash)

	if cash_accounts is not None:
		cash_accounts = list(cash_accounts)
		if bank_cash is None:
			bank_cash = flt(sum(flt(r.get("balance")) for r in cash_accounts))
		else:
			bank_cash = flt(bank_cash)
	elif bank_cash is None:
		# Bank statements use T-1; planning as_of (commitments horizon) stays separate
		from lyqd.cash.bank_cash import default_bank_statement_as_of

		cash_info = get_eligible_bank_cash(company, default_bank_statement_as_of())
		bank_cash = flt(cash_info["total"])
		cash_accounts = cash_info["accounts"]
	else:
		bank_cash = flt(bank_cash)
		cash_accounts = []

	if upcoming_payments is None:
		upcoming_payments = get_planned_upcoming_payments(company, as_of, horizon_days)

	def _signed_commitment(p: dict[str, Any]) -> float:
		"""Outflow grain only (legacy helper for explanation children)."""
		amt = flt(p.get("amount"))
		effect = p.get("cash_effect") or "Outflow"
		if effect in ("Inflow", "Setoff"):
			return 0.0
		return amt

	# Nested GL collapses to group_net — children are not separate commitments/incoming.
	upcoming_total = flt(plan_card_totals(upcoming_payments)["upcoming_total"])

	# Free cash = bank position − commitments − policy reserves
	investable = flt(bank_cash) - upcoming_total - min_liquidity_buffer - restricted_cash

	explanation: list[ExplanationLine] = []
	if cash_accounts:
		for row in cash_accounts:
			bal = flt(row.get("balance"))
			drawn = bal < -0.005
			label = _bank_cash_explanation_label(row, drawn=drawn)
			explanation.append(
				ExplanationLine(
					kind="cash",
					label=label,
					amount=abs(bal),
					sign="-" if drawn else "+",
					ref_doctype="LYQD Bank Account",
					ref_name=row.get("bank_account"),
					notes=f"source={row.get('source')}",
					category=(row.get("account_type") or None),
				)
			)
	else:
		drawn = flt(bank_cash) < -0.005
		explanation.append(
			ExplanationLine(
				kind="cash",
				label="Eligible bank cash" + (" (net drawn)" if drawn else ""),
				amount=abs(flt(bank_cash)),
				sign="-" if drawn else "+",
			)
		)

	def _upcoming_line(p: dict[str, Any], *, signed_net: float | None = None) -> ExplanationLine:
		due = p.get("due_date")
		due_s = str(getdate(due)) if due else None
		title = p.get("title") or p.get("name") or "Upcoming payment"
		overdue = bool(due and getdate(due) < getdate(as_of))
		effect = p.get("cash_effect") or "Outflow"
		own_amt = flt(p.get("amount"))
		own_sign = "-"
		kind_label = "Reserve"
		if signed_net is None:
			disp_amt, disp_sign = own_amt, own_sign
			gl_amount = gl_sign = None
		else:
			# reserved cash > 0 → outflow (−); net setoff/inflow credit → (+)
			disp_amt = abs(flt(signed_net))
			disp_sign = "-" if flt(signed_net) >= 0 else "+"
			gl_amount, gl_sign = own_amt, own_sign
		occ = cint(p.get("occurrence_count") or 0)
		recurring_note = ""
		if cint(p.get("is_recurring")) and occ > 1:
			recurring_note = f"; recurring ×{occ}"
		# Expanded GL schedule lines use a synthetic name; link back to the parent doc
		ref_name = (
			p.get("parent_payment")
			if p.get("_schedule") and p.get("parent_payment")
			else p.get("name")
		)
		return ExplanationLine(
			kind="upcoming",
			label=(
				f"{kind_label} — {title}"
				+ (" (overdue)" if overdue else "")
			),
			amount=disp_amt,
			sign=disp_sign,
			ref_doctype="LYQD Upcoming Payment",
			ref_name=ref_name,
			due_date=due_s,
			category=p.get("category"),
			notes=(p.get("notes") or "")
			+ ("; setoff" if effect == "Setoff" else "")
			+ ("; inflow" if effect == "Inflow" else "")
			+ recurring_note
			+ ("; overdue" if overdue else ""),
			gl_amount=gl_amount,
			gl_sign=gl_sign,
		)

	children_of, child_names = nest_group_maps(upcoming_payments)
	roots: list[dict[str, Any]] = []
	for p in upcoming_payments:
		name = p.get("name")
		if name and name in child_names:
			continue
		if _is_nest_child(p):
			continue
		roots.append(p)

	for root in roots:
		# Standalone incoming roots are shown on Cash position Incoming — not free cash
		kids = children_of.get(root.get("name") or "", []) or []
		if not kids and _cash_effect(root) in ("Inflow", "Setoff"):
			continue
		if kids:
			signed_net = _signed_plan_amount(root) + sum(
				_signed_plan_amount(c) for c in kids
			)
			# Only nest groups that still reserve cash (net outflow) belong in free-cash waterfall
			if signed_net <= 0.01:
				continue
			line = _upcoming_line(root, signed_net=signed_net)
			line.child_count = len(kids)
			line.children = [_upcoming_line(c) for c in kids]
			title = root.get("title") or root.get("name") or "Upcoming payment"
			due = root.get("due_date")
			overdue = bool(due and getdate(due) < getdate(as_of))
			line.label = f"Reserve — {title}" + (" (overdue)" if overdue else "")
			explanation.append(line)
		else:
			explanation.append(_upcoming_line(root))

	if min_liquidity_buffer:
		explanation.append(
			ExplanationLine(
				kind="buffer",
				label="Minimum liquidity buffer (policy)",
				amount=min_liquidity_buffer,
				sign="-",
				ref_doctype="LYQD Company",
				ref_name=policy.get("name"),
			)
		)

	if restricted_cash:
		explanation.append(
			ExplanationLine(
				kind="restricted",
				label="Restricted cash (policy)",
				amount=restricted_cash,
				sign="-",
				ref_doctype="LYQD Company",
				ref_name=policy.get("name"),
			)
		)

	explanation.append(
		ExplanationLine(
			kind="total",
			label="Investable surplus" if investable >= 0 else "Shortfall",
			amount=abs(investable),
			sign="=" if investable >= 0 else "shortfall",
		)
	)

	return SurplusResult(
		company=company,
		as_of=as_of,
		horizon_days=horizon_days,
		horizon_end=horizon_end,
		bank_cash=bank_cash,
		upcoming_total=upcoming_total,
		min_liquidity_buffer=min_liquidity_buffer,
		restricted_cash=restricted_cash,
		investable_surplus=investable,
		is_shortfall=investable < 0,
		explanation=explanation,
		cash_accounts=cash_accounts,
		upcoming_payments=upcoming_payments,
		policy_name=policy.get("name"),
	)


def compute_surplus_comparison(
	company: str,
	as_of: str | None = None,
	horizons: list[int] | None = None,
) -> dict[str, Any]:
	"""Dashboard helper: surplus for 7d and policy/30d horizons."""
	as_of = str(getdate(as_of or today()))
	policy = get_policy(company)
	policy_horizon = int(policy.get("default_forecast_horizon_days") or 7)
	if horizons is None:
		horizons = sorted({7, 30, policy_horizon})

	runs = {str(h): compute_surplus(company, horizon_days=h, as_of=as_of).as_dict() for h in horizons}
	return {
		"company": company,
		"as_of": as_of,
		"policy_horizon_days": policy_horizon,
		"runs": runs,
	}
