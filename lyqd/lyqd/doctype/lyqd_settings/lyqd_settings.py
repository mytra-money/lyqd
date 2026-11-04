# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class LYQDSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		default_forecast_horizon_days: DF.Int
		default_min_liquidity_buffer: DF.Currency
		default_restricted_cash: DF.Currency
		display_scheme_isin: DF.Data | None
		display_scheme_label: DF.Data | None
		enable_draft_proposals: DF.Check
		in_beta: DF.Check
		tagline: DF.Data | None
	# end: auto-generated types

	pass
