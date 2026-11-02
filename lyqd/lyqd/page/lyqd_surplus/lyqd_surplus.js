frappe.pages["lyqd-surplus"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("LYQD Surplus"),
		single_column: true,
	});

	page.set_title(__("LYQD Surplus"));
	page.set_indicator(__("Make idle cash work smarter."), "blue");

	frappe.lyqd_surplus = new lyqd.SurplusPage(page);
};

frappe.pages["lyqd-surplus"].on_page_show = function () {
	if (frappe.lyqd_surplus) {
		frappe.lyqd_surplus.refresh();
	}
};

frappe.provide("lyqd");

lyqd.SurplusPage = class SurplusPage {
	constructor(page) {
		this.page = page;
		this.company = frappe.defaults.get_user_default("Company");
		this.horizon = 7;
		this.make();
		this.refresh();
	}

	make() {
		this.page.add_field({
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: this.company,
			change: () => {
				this.company = this.page.fields_dict.company.get_value();
				this.refresh();
			},
		});

		this.page.add_field({
			fieldname: "horizon_days",
			label: __("Horizon (days)"),
			fieldtype: "Select",
			options: ["7", "30"],
			default: "7",
			change: () => {
				this.horizon = cint(this.page.fields_dict.horizon_days.get_value());
				this.refresh();
			},
		});

		this.page.set_primary_action(__("Refresh"), () => this.refresh());
		this.page.add_inner_button(__("Save Surplus Run"), () => this.save_run());
		this.page.add_inner_button(__("Upcoming Payments"), () =>
			frappe.set_route("List", "LYQD Upcoming Payment")
		);

		this.$body = $(`<div class="lyqd-surplus-page padding">
			<div class="lyqd-hero mb-4">
				<div class="lyqd-brand">LYQD by Mytra</div>
				<div class="lyqd-tagline text-muted">${__("Make idle cash work smarter.")}</div>
			</div>
			<div class="lyqd-summary row"></div>
			<div class="lyqd-explanation mt-4"></div>
		</div>`).appendTo(this.page.main);
	}

	refresh() {
		if (!this.company) {
			this.$body.find(".lyqd-summary").html(
				`<div class="text-muted">${__("Select a Company to compute surplus.")}</div>`
			);
			return;
		}

		frappe.call({
			method: "lyqd.api.dashboard.get_surplus_explanation",
			args: { company: this.company, horizon_days: this.horizon },
			freeze: true,
			freeze_message: __("Computing surplus…"),
		}).then((r) => {
			this.render(r.message);
		});

		// Also load 7d vs 30d comparison strip
		frappe.call({
			method: "lyqd.api.dashboard.get_dashboard_metrics",
			args: { company: this.company },
		}).then((r) => {
			this.render_comparison(r.message);
		});
	}

	render_comparison(metrics) {
		if (!metrics || !metrics.comparison) return;
		const runs = metrics.comparison.runs || {};
		const fmt = (n) => format_currency(n || 0, null, 0);
		const strip = $(`<div class="lyqd-compare alert alert-secondary mt-3">
			<strong>${__("Horizon comparison")}</strong>
			<span class="ml-3">7d: <b>${fmt(runs["7"] && runs["7"].investable_surplus)}</b></span>
			<span class="ml-3">30d: <b>${fmt(runs["30"] && runs["30"].investable_surplus)}</b></span>
			<span class="ml-3 text-muted">${__("Scheme (display only)")}: ${
				frappe.utils.escape_html(metrics.display_scheme_label || "ICICI Prudential Liquid Fund")
			}</span>
		</div>`);
		this.$body.find(".lyqd-compare").remove();
		this.$body.find(".lyqd-hero").after(strip);
	}

	render(result) {
		if (!result) return;
		const fmt = (n) => format_currency(n || 0, null, 0);
		const shortfall = result.is_shortfall;
		const surplus_label = shortfall ? __("Shortfall") : __("Investable surplus");
		const surplus_class = shortfall ? "text-danger" : "text-success";

		this.$body.find(".lyqd-summary").html(`
			<div class="col-sm-3">
				<div class="lyqd-metric">
					<div class="lyqd-metric-label">${__("Bank cash")}</div>
					<div class="lyqd-metric-value">${fmt(result.bank_cash)}</div>
				</div>
			</div>
			<div class="col-sm-3">
				<div class="lyqd-metric">
					<div class="lyqd-metric-label">${__("Upcoming")} (${result.horizon_days}d)</div>
					<div class="lyqd-metric-value">${fmt(result.upcoming_total)}</div>
				</div>
			</div>
			<div class="col-sm-3">
				<div class="lyqd-metric">
					<div class="lyqd-metric-label">${__("Buffer + restricted")}</div>
					<div class="lyqd-metric-value">${fmt(
						(result.min_liquidity_buffer || 0) + (result.restricted_cash || 0)
					)}</div>
				</div>
			</div>
			<div class="col-sm-3">
				<div class="lyqd-metric lyqd-metric-primary">
					<div class="lyqd-metric-label">${surplus_label}</div>
					<div class="lyqd-metric-value ${surplus_class}">${fmt(
			Math.abs(result.investable_surplus || 0)
		)}</div>
				</div>
			</div>
		`);

		const rows = (result.explanation || [])
			.map((line) => {
				const due = line.due_date
					? `<span class="text-muted">${frappe.datetime.str_to_user(line.due_date)}</span>`
					: "";
				const cat = line.category
					? `<span class="badge badge-secondary">${frappe.utils.escape_html(line.category)}</span>`
					: "";
				const ref = line.ref_name
					? `<a href="/app/${frappe.scrub(line.ref_doctype).replace(/_/g, "-")}/${encodeURIComponent(
							line.ref_name
					  )}">${frappe.utils.escape_html(line.ref_name)}</a>`
					: "";
				return `<tr>
					<td>${frappe.utils.escape_html(line.sign || "")}</td>
					<td>${frappe.utils.escape_html(line.label || "")} ${cat} ${due} ${ref}</td>
					<td class="text-right">${fmt(line.amount)}</td>
				</tr>`;
			})
			.join("");

		this.$body.find(".lyqd-explanation").html(`
			<h5>${__("Explanation")}</h5>
			<p class="text-muted">
				${__("As of")} ${frappe.datetime.str_to_user(result.as_of)} ·
				${__("Horizon ends")} ${frappe.datetime.str_to_user(result.horizon_end)} ·
				${__("Only Planned upcoming payments are reserved.")}
			</p>
			<table class="table table-bordered lyqd-explain-table">
				<thead>
					<tr>
						<th style="width:4rem"></th>
						<th>${__("Item")}</th>
						<th class="text-right">${__("Amount")}</th>
					</tr>
				</thead>
				<tbody>${rows}</tbody>
			</table>
		`);
	}

	save_run() {
		if (!this.company) {
			frappe.msgprint(__("Select a Company first"));
			return;
		}
		frappe.call({
			method: "lyqd.api.dashboard.save_surplus_run",
			args: { company: this.company, horizon_days: this.horizon },
			freeze: true,
		}).then((r) => {
			frappe.set_route("Form", "LYQD Surplus Run", r.message);
		});
	}
};
