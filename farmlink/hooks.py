app_name = "farmlink"
app_title = "FarmLink"
app_publisher = "vulerotech"
app_description = "Digital coffee management platform"
app_email = "mezmure.dawit@vulero.et"
app_license = "mit"
app_logo_url = "/assets/farmlink/images/farmlink_icon.png"

add_to_apps_screen = [
	{
		"name": "farmlink",
		"logo": "/assets/farmlink/images/farmlink_icon.png",
		"title": "FarmLink",
		"route": "/app",
	}
]

# Fixtures
# --------
# Ship default Receipt String rows on install/migrate so fresh deployments
# print receipts identical to the previous hardcoded layout out of the box.
# Existing rows are NOT overwritten on subsequent migrates — admins keep their
# edits. To restore a default, delete the row and re-run `bench migrate`.
fixtures = [
	{
		"dt": "Receipt String",
		"filters": [["target_doctype", "in", ["Purchases", "Payment", "Primary Arrival Log"]]],
	},
]

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "farmlink",
# 		"logo": "/assets/farmlink/logo.png",
# 		"title": "FarmLink",
# 		"route": "/farmlink",
# 		"has_permission": "farmlink.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = ["/assets/farmlink/css/sidebar_theme.css"]
app_include_js = [
	"/assets/farmlink/js/read_scale.js",
	"/assets/farmlink/js/farms_geo_google.js",
	"/assets/farmlink/js/farm_map_widget.js",
]

# include js, css files in header of web template
# web_include_css = "/assets/farmlink/css/farmlink.css"
# web_include_js = "/assets/farmlink/js/farmlink.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "farmlink/public/scss/website"
boot_session = "farmlink.utils.boot.boot_session"
#doc_events = {
#    "Farmer": {
#        "after_insert": "farmlink.utils.farmlink_sync.on_farmer_change",
#        "on_update": "farmlink.utils.farmlink_sync.on_farmer_change",
#        "on_trash": "farmlink.utils.farmlink_sync.on_farmer_change"
#    },
#    "Payment": {
#        "after_insert": "farmlink.utils.farmlink_sync.on_payment_change",
#        "on_update": "farmlink.utils.farmlink_sync.on_payment_change",
#        "on_trash": "farmlink.utils.farmlink_sync.on_payment_change"
#    },
#    "Purchase": {
#        "after_insert": "farmlink.utils.farmlink_sync.on_purchase_change",
#        "on_update": "farmlink.utils.farmlink_sync.on_purchase_change",
#        "on_trash": "farmlink.utils.farmlink_sync.on_purchase_change"
#    },
#    "Territory": {
#        "after_insert": "farmlink.utils.farmlink_sync.on_territory_change",
#        "on_update": "farmlink.utils.farmlink_sync.on_territory_change",
#        "on_trash": "farmlink.utils.farmlink_sync.on_territory_change"
#    },
#    "Washing Station": {
#        "after_insert": "farmlink.utils.farmlink_sync.on_washing_station_change",
#        "on_update": "farmlink.utils.farmlink_sync.on_washing_station_change",
#        "on_trash": "farmlink.utils.farmlink_sync.on_washing_station_change"
#    }
#}

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
#doctype_js = {"Farms": "/assets/farmlink/js/farms_geo_google.js"}

#doctype_js = {"Farms" : "public/js/farms_geo_google.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "farmlink/public/icons/farmlink_icon.svg"

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
# 	"methods": "farmlink.utils.jinja_methods",
# 	"filters": "farmlink.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "farmlink.install.before_install"
after_install = "farmlink.install.after_install"
after_migrate = ["farmlink.install.after_migrate"]

# Uninstallation
# ------------

# before_uninstall = "farmlink.uninstall.before_uninstall"
# after_uninstall = "farmlink.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "farmlink.install.before_app_install"
# after_app_install = "farmlink.install.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "farmlink.install.before_app_uninstall"
# after_app_uninstall = "farmlink.install.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "farmlink.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
	"Farmers": "farmlink.sync.permissions.get_for_farmers",
	"Farms": "farmlink.sync.permissions.get_for_farms",
	"Purchases": "farmlink.sync.permissions.get_for_purchases",
	"Payment": "farmlink.sync.permissions.get_for_payment",
	"Primary Arrival Log": "farmlink.sync.permissions.get_for_primary_arrival_log",
	"Primary Dispatch": "farmlink.sync.permissions.get_for_primary_dispatch",
	"Primary Processing": "farmlink.sync.permissions.get_for_primary_processing",
	"Secondary Processing": "farmlink.sync.permissions.get_for_secondary_processing",
	"Secondary Arrival Log": "farmlink.sync.permissions.get_for_secondary_arrival_log",
	"Export Arrival Log": "farmlink.sync.permissions.get_for_export_arrival_log",
	"Cupping Order": "farmlink.sync.permissions.get_for_cupping_order",
	"Trades": "farmlink.sync.permissions.get_for_trades",
	"Export Dispatch": "farmlink.sync.permissions.get_for_export_dispatch",
	"Centers": "farmlink.sync.permissions.get_for_centers",
	"Territory": "farmlink.sync.permissions.get_for_territory",
	"Supplier": "farmlink.sync.permissions.get_for_supplier",
	"Personnel": "farmlink.sync.permissions.get_for_personnel",
	"Receipt String": "farmlink.sync.permissions.get_for_receipt_string",
}

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Payment": {
		"after_insert": "farmlink.hook_handlers.on_payment_change",
		"on_update": "farmlink.hook_handlers.on_payment_change",
		"on_trash": [
			"farmlink.hook_handlers.on_payment_change",
			"farmlink.sync.tombstones.record_tombstone",
		],
	},
	"Primary Arrival Log": {
		"on_update": "farmlink.supply_chain.stock_ledger.primary_arrival_on_save",
		"on_trash": [
			"farmlink.supply_chain.stock_ledger.primary_arrival_on_trash",
			"farmlink.sync.tombstones.record_tombstone",
		],
	},
	"Primary Processing": {
		"on_update": "farmlink.supply_chain.stock_ledger.primary_processing_on_save",
		"on_trash": [
			"farmlink.supply_chain.stock_ledger.primary_processing_on_trash",
			"farmlink.sync.tombstones.record_tombstone",
		],
	},
	"Primary Dispatch": {
		"on_update": "farmlink.supply_chain.stock_ledger.primary_dispatch_on_save",
		"on_trash": [
			"farmlink.supply_chain.stock_ledger.primary_dispatch_on_trash",
			"farmlink.sync.tombstones.record_tombstone",
		],
	},
	"Secondary Arrival Log": {
		"on_update": "farmlink.supply_chain.stock_ledger.secondary_arrival_on_save",
		"on_trash": [
			"farmlink.supply_chain.stock_ledger.secondary_arrival_on_trash",
			"farmlink.sync.tombstones.record_tombstone",
		],
	},
	"Secondary Processing": {
		"on_update": "farmlink.supply_chain.stock_ledger.secondary_processing_on_save",
		"on_trash": [
			"farmlink.supply_chain.stock_ledger.secondary_processing_on_trash",
			"farmlink.sync.tombstones.record_tombstone",
		],
	},
	"Export Arrival Log": {
		"on_update": "farmlink.supply_chain.stock_ledger.export_arrival_on_save",
		"on_trash": [
			"farmlink.supply_chain.stock_ledger.export_arrival_on_trash",
			"farmlink.sync.tombstones.record_tombstone",
		],
	},
	"Trades": {
		"on_update": "farmlink.supply_chain.stock_ledger.trades_on_save",
		"on_trash": [
			"farmlink.supply_chain.stock_ledger.trades_on_trash",
			"farmlink.sync.tombstones.record_tombstone",
		],
	},
	"Export Dispatch": {
		"on_update": "farmlink.supply_chain.stock_ledger.export_dispatch_on_save",
		"on_trash": [
			"farmlink.supply_chain.stock_ledger.export_dispatch_on_trash",
			"farmlink.sync.tombstones.record_tombstone",
		],
	},
	"Farmers": {
		"on_trash": "farmlink.sync.tombstones.record_tombstone",
	},
	"Farms": {
		"on_trash": "farmlink.sync.tombstones.record_tombstone",
	},
	"Purchases": {
		"on_trash": "farmlink.sync.tombstones.record_tombstone",
	},
	"Territory": {
		"on_trash": "farmlink.sync.tombstones.record_tombstone",
	},
	"Centers": {
		"on_trash": "farmlink.sync.tombstones.record_tombstone",
	},
	"Supplier": {
		"on_trash": "farmlink.sync.tombstones.record_tombstone",
	},
	"Cupping Order": {
		"on_trash": "farmlink.sync.tombstones.record_tombstone",
	},
	"Personnel": {
		"on_update": "farmlink.hook_handlers.on_personnel_update",
		"on_trash": "farmlink.sync.tombstones.record_tombstone",
	},
}

# Scheduled Tasks
# ----------

# scheduler_events = {
# 	"all": [
# 		"farmlink.tasks.all"
# 	],
# 	"daily": [
# 		"farmlink.tasks.daily"
# 	],
# 	"hourly": [
# 		"farmlink.tasks.hourly"
# 	],
# 	"weekly": [
# 		"farmlink.tasks.weekly"
# 	],
# 	"monthly": [
# 		"farmlink.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "farmlink.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "farmlink.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "farmlink.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["farmlink.utils.before_request"]
# after_request = ["farmlink.utils.before_request"]
# after_request = ["farmlink.utils.after_request"]

# Job Events
# ----------
# before_job = ["farmlink.utils.before_job"]
# after_job = ["farmlink.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
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
# 	"farmlink.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# API Methods
# -----------
# Add custom API methods that can be called from the desk

# whitelist = [
# 	"farmlink.utils.refresh_all_purchase_payment_statuses",
# 	"farmlink.utils.force_update_purchase_payment_status"
# ]
