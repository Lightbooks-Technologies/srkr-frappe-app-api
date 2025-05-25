app_name = "srkr_frappe_app_api"
app_title = "Srkr Frappe App Api"
app_publisher = "LB"
app_description = "Srkr frappe app api"
app_email = "info@lightbooks.io"
app_license = "mit"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/srkr_frappe_app_api/css/srkr_frappe_app_api.css"
# app_include_js = "/assets/srkr_frappe_app_api/js/srkr_frappe_app_api.js"

# include js, css files in header of web template
# web_include_css = "/assets/srkr_frappe_app_api/css/srkr_frappe_app_api.css"
# web_include_js = "/assets/srkr_frappe_app_api/js/srkr_frappe_app_api.js"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "srkr_frappe_app_api.install.before_install"
# after_install = "srkr_frappe_app_api.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "srkr_frappe_app_api.uninstall.before_uninstall"
# after_uninstall = "srkr_frappe_app_api.uninstall.after_uninstall"

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"srkr_frappe_app_api.tasks.all"
# 	],
# 	"daily": [
# 		"srkr_frappe_app_api.tasks.daily"
# 	],
# 	"hourly": [
# 		"srkr_frappe_app_api.tasks.hourly"
# 	],
# 	"weekly": [
# 		"srkr_frappe_app_api.tasks.weekly"
# 	],
# 	"monthly": [
# 		"srkr_frappe_app_api.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "srkr_frappe_app_api.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "srkr_frappe_app_api.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "srkr_frappe_app_api.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["srkr_frappe_app_api.utils.before_request"]
# after_request = ["srkr_frappe_app_api.utils.after_request"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"srkr_frappe_app_api.auth.validate"
# ]