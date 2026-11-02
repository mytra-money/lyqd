// Copyright (c) 2026, Mytra and contributors
// For license information, please see license.txt

frappe.ui.form.on("LYQD Upcoming Payment", {
	refresh(frm) {
		frm.set_intro(
			__("Committed forecast only. Planned rows reserve surplus until Paid or Cancelled."),
			"blue"
		);
	},
});
