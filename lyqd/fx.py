"""Convert book / statement amounts into LYQD Company currency for surplus math."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import flt, getdate, today


def get_lyqd_company_currency(company: str | None) -> str:
	if not company:
		return "INR"
	return (frappe.db.get_value("LYQD Company", company, "default_currency") or "INR").upper()


def convert_amount(
	amount: float | int | str | None,
	from_currency: str | None,
	to_currency: str | None,
	as_of: str | None = None,
	*,
	conversion_rate: float | int | str | None = None,
	args: str = "for_buying",
) -> float:
	"""Convert ``amount`` from ``from_currency`` into ``to_currency``.

	Prefers an explicit ``conversion_rate`` (e.g. invoice rate). Otherwise uses
	ERPNext Currency Exchange when available.
	"""
	amt = flt(amount)
	src = (from_currency or to_currency or "INR").upper()
	dst = (to_currency or "INR").upper()
	if not amt or src == dst:
		return amt

	rate = flt(conversion_rate)
	if rate:
		return flt(amt * rate)

	try:
		from erpnext.setup.utils import get_exchange_rate

		rate = flt(
			get_exchange_rate(src, dst, str(getdate(as_of or today())), args=args) or 0
		)
	except Exception:
		frappe.log_error(title="LYQD FX conversion failed")
		rate = 0

	if not rate:
		frappe.throw(
			frappe._(
				"No exchange rate from {0} to {1} for {2}. "
				"Add a Currency Exchange entry, then retry."
			).format(src, dst, getdate(as_of or today()))
		)
	return flt(amt * rate)


def _row_get(row: dict[str, Any] | Any, key: str, default: Any = None) -> Any:
	if isinstance(row, dict):
		return row.get(key, default)
	if hasattr(row, "get"):
		return row.get(key, default)
	return getattr(row, key, default)


def invoice_outstanding_in_company_currency(
	row: dict[str, Any] | Any,
	company_currency: str,
	*,
	as_of: str | None = None,
) -> float:
	"""Purchase / Sales Invoice outstanding → company currency.

	ERPNext stores ``outstanding_amount`` in ``party_account_currency``. When that
	differs from company currency, multiply by the invoice ``conversion_rate``.
	"""
	outstanding = flt(_row_get(row, "outstanding_amount"))
	party_ccy = (
		_row_get(row, "party_account_currency")
		or _row_get(row, "currency")
		or company_currency
		or "INR"
	).upper()
	company_ccy = (company_currency or "INR").upper()
	if party_ccy == company_ccy:
		return outstanding
	return convert_amount(
		outstanding,
		party_ccy,
		company_ccy,
		as_of or _row_get(row, "due_date") or _row_get(row, "posting_date"),
		conversion_rate=_row_get(row, "conversion_rate"),
	)
