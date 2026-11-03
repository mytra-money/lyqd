// Copyright (c) 2026, Mytra and contributors
// For license information, please see license.txt

frappe.ui.form.on("LYQD Surplus Run", {
	refresh(frm) {
		frm.disable_save();
		frm.set_intro(
			__("Immutable free-cash calculation. Investment requests link to this run."),
			"blue"
		);
		frm.add_custom_button(__("Open LYQD"), () => {
			window.open("/lyqd/surplus", "_blank");
		});
		if (!frm.is_new()) {
			frm.add_custom_button(__("Open investment requests"), () => {
				frappe.set_route("List", "LYQD Draft Proposal", {
					surplus_run: frm.doc.name,
				});
			});
		}
	},
});
