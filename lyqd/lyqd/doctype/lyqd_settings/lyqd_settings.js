// Copyright (c) 2026, Mytra and contributors
// For license information, please see license.txt

frappe.ui.form.on("LYQD Settings", {
	refresh(frm) {
		frm.set_intro(
			__("PoC settings only — no BSE / Mytra execution. Make idle cash work smarter."),
			"blue"
		);
	},
});
