// Copyright (c) 2026, Mytra and contributors
// For license information, please see license.txt

frappe.ui.form.on("LYQD Policy", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Open Surplus"), () => {
				frappe.set_route("lyqd-surplus", {
					company: frm.doc.company,
				});
			});
		}
	},
});
