// Copyright (c) 2026, Mytra and contributors
// For license information, please see license.txt

frappe.ui.form.on("LYQD Draft Proposal", {
	refresh(frm) {
		frm.set_intro(
			__("Invest or Redeem request based on a Surplus Run. Create an instruction when confirmed."),
			"blue"
		);
		if (!frm.is_new() && frm.doc.surplus_run) {
			frm.add_custom_button(__("Open Surplus Run"), () => {
				frappe.set_route("Form", "LYQD Surplus Run", frm.doc.surplus_run);
			});
		}
		if (!frm.is_new() && frm.doc.status === "Draft") {
			frm.add_custom_button(__("Confirm amount"), () => {
				frm.call("freeze_from_surplus").then(() => {
					frm.reload_doc();
					frappe.show_alert({ message: __("Request confirmed"), indicator: "green" });
				});
			});
		}
		if (!frm.is_new() && frm.doc.status === "Frozen") {
			frm.add_custom_button(
				__("Create instruction"),
				() => {
					frappe
						.call({
							method: "lyqd.api.spa.create_instruction_from_proposal",
							args: { proposal: frm.doc.name },
						})
						.then((r) => {
							const name = r.message && r.message.name;
							frappe.show_alert({
								message: __("Instruction {0} created", [name || ""]),
								indicator: "green",
							});
							if (name) {
								frappe.set_route("Form", "LYQD Investment Instruction", name);
							}
						});
				},
				__("Actions")
			);
		}
	},
});
