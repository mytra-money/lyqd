app_name = "lyqd"
app_title = "LYQD by Mytra"
app_publisher = "Mytra"
app_description = "Corporate surplus-cash for ERPNext — policy, upcoming payments, explainable investable surplus"
app_email = "hello@mytra.money"
app_license = "mit"
app_home = "/lyqd"

# ERPNext is optional (This Site books). Other Site / Manual work on Frappe + LYQD only.
required_apps = ["frappe"]

add_to_apps_screen = [
	{
		"name": "lyqd",
		"logo": "/assets/lyqd/images/lyqd.svg?v=3",
		"title": "LYQD by Mytra",
		"route": "/lyqd",
		"has_permission": "lyqd.setup.permissions.has_app_permission",
	}
]

app_include_css = "/assets/lyqd/css/lyqd.css"

website_route_rules = [
	{"from_route": "/lyqd/<path:app_path>", "to_route": "lyqd"},
	{"from_route": "/lyqd", "to_route": "lyqd"},
]

after_install = "lyqd.setup.install.after_install"
after_migrate = "lyqd.setup.install.after_migrate"

# Company-scoped list filters (permission query)
permission_query_conditions = {
	"LYQD Company": "lyqd.setup.permissions.get_lyqd_company_list_query",
	"LYQD Bank Account": "lyqd.setup.permissions.get_lyqd_bank_account_query",
	"LYQD Policy": "lyqd.setup.permissions.get_lyqd_policy_query",
	"LYQD Upcoming Payment": "lyqd.setup.permissions.get_lyqd_upcoming_payment_query",
	"LYQD Surplus Run": "lyqd.setup.permissions.get_lyqd_surplus_run_query",
	"LYQD Cash Snapshot": "lyqd.setup.permissions.get_lyqd_cash_snapshot_query",
	"LYQD Draft Proposal": "lyqd.setup.permissions.get_lyqd_draft_proposal_query",
	"LYQD Investment Instruction": "lyqd.setup.permissions.get_lyqd_instruction_query",
	"LYQD Holding": "lyqd.setup.permissions.get_lyqd_holding_query",
}

has_permission = {
	"LYQD Company": "lyqd.setup.permissions.has_company_permission",
	"LYQD Bank Account": "lyqd.setup.permissions.has_company_permission",
	"LYQD Policy": "lyqd.setup.permissions.has_company_permission",
	"LYQD Upcoming Payment": "lyqd.setup.permissions.has_company_permission",
	"LYQD Surplus Run": "lyqd.setup.permissions.has_company_permission",
	"LYQD Cash Snapshot": "lyqd.setup.permissions.has_company_permission",
	"LYQD Draft Proposal": "lyqd.setup.permissions.has_company_permission",
	"LYQD Investment Instruction": "lyqd.setup.permissions.has_company_permission",
	"LYQD Holding": "lyqd.setup.permissions.has_company_permission",
}

fixtures = []
