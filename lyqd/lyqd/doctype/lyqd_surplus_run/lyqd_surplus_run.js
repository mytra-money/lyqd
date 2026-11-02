// Copyright (c) 2026, Mytra and contributors
// For license information, please see license.txt

frappe.ui.form.on("LYQD Surplus Run", {
	refresh(frm) {
		frm.add_custom_button(__("Recalculate"), () => {
			frm.call("recalculate").then(() => {
				frm.refresh();
				frappe.show_alert({ message: __("Surplus recalculated"), indicator: "green" });
			});
		});
		frm.add_custom_button(__("Open Surplus Page"), () => {
			frappe.set_route("lyqd-surplus");
		});
	},
});
