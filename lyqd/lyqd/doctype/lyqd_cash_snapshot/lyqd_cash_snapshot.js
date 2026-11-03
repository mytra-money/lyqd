// Copyright (c) 2026, Mytra and contributors
// For license information, please see license.txt

frappe.ui.form.on("LYQD Cash Snapshot", {
	refresh(frm) {
		frm.set_intro(
			__(
				"Legacy. Prefer updating balances from /lyqd/cash (writes LYQD Bank Balance directly)."
			),
			"orange"
		);
	},
});
