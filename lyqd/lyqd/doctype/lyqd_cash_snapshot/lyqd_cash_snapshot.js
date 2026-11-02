// Copyright (c) 2026, Mytra and contributors
// For license information, please see license.txt

frappe.ui.form.on("LYQD Cash Snapshot", {
	refresh(frm) {
		frm.set_intro(
			__(
				"Fast cash update linked to an ERPNext Bank Account. Not a parallel cash ledger — surplus reads these figures (or Bank Account Balance / GL when available)."
			),
			"blue"
		);
	},
	bank_account(frm) {
		if (!frm.doc.bank_account) return;
		frappe.db.get_value("Bank Account", frm.doc.bank_account, ["company", "account"]).then((r) => {
			if (r.message) {
				if (r.message.company) frm.set_value("company", r.message.company);
				if (r.message.account) frm.set_value("gl_account", r.message.account);
			}
		});
	},
});
