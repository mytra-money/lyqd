"""Recurring plan series on LYQD Upcoming Payment (single row, live horizon expand).

Supports manual **Outflow** and **Inflow** series (not Setoff / books-sourced rows).
Outflows reserve free cash; inflows expand into expected incoming only.

**Daily catch-up:** overdue Daily next-due snaps to ``as_of`` on MIS / plan load
(missed days skipped). **Record daily** (mark paid) then advances to tomorrow.

JS mirror (expand math): ``apps/lyqd/frontend/src/utils/recurrence.js``.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import add_days, add_months, cint, flt, getdate


FREQUENCIES = ("Daily", "Weekly", "Monthly", "Quarterly")


def next_due_after(due: str, frequency: str) -> str:
	"""Advance one period from ``due``."""
	d = getdate(due)
	freq = (frequency or "Monthly").strip()
	if freq == "Daily":
		return str(add_days(d, 1))
	if freq == "Weekly":
		return str(add_days(d, 7))
	if freq == "Quarterly":
		return str(add_months(d, 3))
	return str(add_months(d, 1))


def iter_occurrence_dates(
	next_due: str,
	frequency: str,
	as_of: str,
	horizon_end: str,
	recurrence_end: str | None = None,
) -> list[str]:
	"""Dates from next_due stepping forward while date <= horizon_end (and optional end)."""
	_ = as_of  # overdue next_due (< as_of) is still included if <= horizon_end
	cursor = getdate(next_due)
	end = getdate(horizon_end)
	stop = getdate(recurrence_end) if recurrence_end else None
	if stop and cursor > stop:
		return []
	out: list[str] = []
	guard = 0
	while cursor <= end and guard < 400:
		if stop and cursor > stop:
			break
		out.append(str(cursor))
		cursor = getdate(next_due_after(str(cursor), frequency))
		guard += 1
	return out


def expand_recurring_row(
	row: dict[str, Any],
	as_of: str,
	horizon_days: int,
) -> dict[str, Any]:
	"""Annotate a Planned row with horizon totals for recurring series.

	``amount`` becomes the horizon reserve total; ``period_amount`` keeps the per-cycle figure.
	"""
	period = flt(row.get("amount"))
	row["period_amount"] = period
	row["occurrence_count"] = 1
	row["occurrence_dates"] = [str(getdate(row.get("due_date")))] if row.get("due_date") else []

	if not cint(row.get("is_recurring")):
		return row

	frequency = (row.get("frequency") or "Monthly").strip()
	if frequency not in FREQUENCIES:
		frequency = "Monthly"
	if not row.get("due_date"):
		return row

	horizon_end = str(add_days(getdate(as_of), int(horizon_days)))
	dates = iter_occurrence_dates(
		str(row["due_date"]),
		frequency,
		str(as_of),
		horizon_end,
		row.get("recurrence_end"),
	)
	if not dates:
		row["amount"] = 0.0
		row["occurrence_count"] = 0
		row["occurrence_dates"] = []
		return row

	row["occurrence_dates"] = dates
	row["occurrence_count"] = len(dates)
	row["amount"] = flt(period * len(dates))
	return row


def advance_recurring_after_paid(payment) -> None:
	"""Roll next due forward; keep series Planned (GL-style, not voucher Paid).

	For Daily series, first snap overdue next-due to today so one "Record daily"
	moves yesterday → today → tomorrow (not +1 from a stale past due).
	"""
	if not cint(getattr(payment, "is_recurring", 0)):
		return
	freq = (getattr(payment, "frequency", None) or "Monthly").strip()
	if freq not in FREQUENCIES:
		freq = "Monthly"

	from frappe.utils import today

	as_of = getdate(today())
	due = getdate(payment.due_date) if payment.due_date else as_of
	# Daily catch-up before advance: missed days are skipped
	if freq == "Daily" and due < as_of:
		due = as_of

	payment.due_date = next_due_after(str(due), freq)
	payment.status = "Planned"
	# Optional end: if next due past end, cancel series
	end = getattr(payment, "recurrence_end", None)
	if end and getdate(payment.due_date) > getdate(end):
		payment.status = "Cancelled"
		payment.notes = (payment.notes or "") + (
			("\n" if payment.notes else "") + "Series ended after last paid cycle."
		)


def catch_up_daily_recurring(company: str, as_of: str | None = None) -> int:
	"""Persist Daily series next-due when it has fallen behind ``as_of``.

	Missed days are skipped (not stacked as expected cash). Returns rows updated.
	Call before horizon expand / MIS so charts and plan lists stay on today.
	"""
	if not company or not frappe.db.exists("DocType", "LYQD Upcoming Payment"):
		return 0

	as_of_s = str(getdate(as_of) if as_of else frappe.utils.today())
	rows = frappe.get_all(
		"LYQD Upcoming Payment",
		filters={
			"company": company,
			"status": "Planned",
			"is_recurring": 1,
			"frequency": "Daily",
			"due_date": ("<", as_of_s),
		},
		fields=["name", "due_date", "recurrence_end"],
	)
	updated = 0
	for row in rows:
		new_due = as_of_s
		end = row.get("recurrence_end")
		values: dict[str, Any] = {"due_date": new_due}
		if end and getdate(new_due) > getdate(end):
			values["status"] = "Cancelled"
		frappe.db.set_value(
			"LYQD Upcoming Payment",
			row.name,
			values,
			update_modified=True,
		)
		updated += 1
	return updated
