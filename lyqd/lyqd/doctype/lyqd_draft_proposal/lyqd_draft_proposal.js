// Copyright (c) 2026, Mytra and contributors
// For license information, please see license.txt

frappe.ui.form.on("LYQD Draft Proposal", {
	refresh(frm) {
		frm.set_intro(
			__("Draft only — freezes surplus numbers. No Mytra / BSE submit in this PoC."),
			"orange"
		);
		if (!frm.is_new() && frm.doc.status !== "Frozen") {
			frm.add_custom_button(__("Freeze Numbers"), () => {
				frm.call("freeze_from_surplus").then(() => {
					frm.reload_doc();
					frappe.show_alert({ message: __("Proposal frozen"), indicator: "green" });
				});
			});
		}
	},
});
