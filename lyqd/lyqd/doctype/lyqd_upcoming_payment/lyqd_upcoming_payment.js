// Copyright (c) 2026, Mytra and contributors
// For license information, please see license.txt

frappe.ui.form.on("LYQD Upcoming Payment", {
	refresh(frm) {
		frm.set_intro(
			__("Committed forecast only. Planned rows reserve surplus until Paid or Cancelled."),
			"blue"
		);
		frm.set_query("category", () => {
			const filters = {
				company: frm.doc.company,
				disabled: 0,
			};
			if (frm.doc.cash_effect === "Outflow") {
				filters.allow_outflow = 1;
			} else if (frm.doc.cash_effect === "Inflow" || frm.doc.cash_effect === "Setoff") {
				filters.allow_inflow = 1;
			}
			return { filters };
		});
	},
	company(frm) {
		if (frm.doc.category) {
			frm.set_value("category", null);
		}
	},
	cash_effect(frm) {
		// Clear category when direction no longer matches
		if (!frm.doc.category || !frm.doc.cash_effect) return;
		frappe.db.get_value(
			"LYQD Payment Category",
			frm.doc.category,
			["allow_outflow", "allow_inflow"],
			(r) => {
				if (!r) return;
				const effect = frm.doc.cash_effect;
				const ok =
					(effect === "Outflow" && cint(r.allow_outflow)) ||
					((effect === "Inflow" || effect === "Setoff") && cint(r.allow_inflow));
				if (!ok) frm.set_value("category", null);
			}
		);
	},
});
