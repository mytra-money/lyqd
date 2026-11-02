# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class LYQDScheme(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amc: DF.Data | None
		category: DF.Literal["Liquid", "Overnight", "Ultra Short", "Other"]
		description: DF.SmallText | None
		is_active: DF.Check
		is_default: DF.Check
		isin: DF.Data
		notes: DF.SmallText | None
		scheme_name: DF.Data
	# end: auto-generated types

	pass
