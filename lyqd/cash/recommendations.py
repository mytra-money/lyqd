"""Backward-compatible imports — implementation lives in ``lyqd.recommendations``."""

from lyqd.recommendations import (  # noqa: F401
	accept_recommendation,
	get_liability_recommendations,
	get_purchase_invoice_recommendations,
	get_recommendation_account_rows,
	is_erpnext_integration_enabled,
	resolve_books_outstanding,
	sync_planned_from_books,
	sync_upcoming_payment_from_books,
)
