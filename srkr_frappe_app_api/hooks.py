# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "srkr_frappe_app_api"
app_title = "Srkr Frappe App Api"
app_publisher = "LB"
app_description = "Srkr frappe app api"
app_email = "info@lightbooks.io"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "srkr_frappe_app_api",
# 		"logo": "/assets/srkr_frappe_app_api/logo.png",
# 		"title": "Srkr Frappe App Api",
# 		"route": "/srkr_frappe_app_api",
# 		"has_permission": "srkr_frappe_app_api.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/srkr_frappe_app_api/css/srkr_frappe_app_api.css"
# app_include_js = "/assets/srkr_frappe_app_api/js/srkr_frappe_app_api.js"

# include js, css files in header of web template
# web_include_css = "/assets/srkr_frappe_app_api/css/srkr_frappe_app_api.css"
# web_include_js = "/assets/srkr_frappe_app_api/js/srkr_frappe_app_api.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "srkr_frappe_app_api/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Student": "public/js/student_exam_results.js",
    "Semester Midterm Assessment": "public/js/semester_midterm_assessment.js",
    "Bulk Assessment Creator": "public/js/bulk_assessment_creator.js"
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "srkr_frappe_app_api/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "srkr_frappe_app_api.utils.jinja_methods",
# 	"filters": "srkr_frappe_app_api.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "srkr_frappe_app_api.install.before_install"
# after_install = "srkr_frappe_app_api.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "srkr_frappe_app_api.uninstall.before_uninstall"
# after_uninstall = "srkr_frappe_app_api.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "srkr_frappe_app_api.utils.before_app_install"
# after_app_install = "srkr_frappe_app_api.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "srkr_frappe_app_api.utils.before_app_uninstall"
# after_app_uninstall = "srkr_frappe_app_api.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "srkr_frappe_app_api.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
    "Exam Semester Result": "srkr_frappe_app_api.examination.permissions.get_permission_query_conditions",
    "Exam Semester Backlog": "srkr_frappe_app_api.examination.permissions.get_permission_query_conditions",
    "Exam HM Semester Result": "srkr_frappe_app_api.examination.permissions.get_permission_query_conditions",
}
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
    "Course Scheduling Tool": "srkr_frappe_app_api.overrides.CustomCourseSchedulingTool"
}

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

scheduler_events = {
# 	"all": [
# 		"srkr_frappe_app_api.tasks.all"
# 	],
	"daily": [
		"srkr_frappe_app_api.examination.tasks.sync_all_active_students"
	],
    "cron": {
        # This is your existing job that runs at 6:00 PM
        "0 18 * * *": [
            "srkr_frappe_app_api.instructor.api.send_daily_attendance_summary"
        ],
        # "10 17 * * *": [  # Runs at 5:10 PM for instructor reminders
        #     "srkr_frappe_app_api.instructor.api.send_instructor_attendance_reminders"
        # ],
        # This is your new job that runs at 5:00 PM (17:00) server time every day
        "0 17 * * *": [
            "srkr_frappe_app_api.srkr_frappe_app_api.report.daily_attendance_status.daily_attendance_status.send_daily_attendance_report"
        ],
        # This is your new job that runs at 6:15 PM (18:15) server time every day
        "15 18 * * *": [
            "srkr_frappe_app_api.srkr_frappe_app_api.report.daily_attendance_status.daily_attendance_status.send_daily_attendance_report_to_main_admin"
        ],
        "20 17 * * *": [
            "srkr_frappe_app_api.instructor.api.sync_external_attendance" 
        ]
    }
# 	"hourly": [
# 		"srkr_frappe_app_api.tasks.hourly"
# 	],
# 	"weekly": [
# 		"srkr_frappe_app_api.tasks.weekly"
# 	],
# 	"monthly": [
# 		"srkr_frappe_app_api.tasks.monthly"
# 	],
}

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

# Job Events
# ----------
# before_job = ["srkr_frappe_app_api.utils.before_job"]
# after_job = ["srkr_frappe_app_api.utils.after_job"]

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

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }