# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class LYQDUpcomingSplit(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amount: DF.Currency
		due_date: DF.Date
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		probability: DF.Percent | None
		status: DF.Literal["Planned", "Paid"]
		title: DF.Data | None
	# end: auto-generated types

	pass
