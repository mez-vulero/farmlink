# FarmLink Frappe App Hooks Configuration

app_name = "farmlink"
app_title = "FarmLink"
app_publisher = "Your Company"
app_description = "Supply Chain Management for Coffee Farmers"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "admin@farmlink.et"
app_license = "MIT"

# API endpoints for WatermelonDB sync
# These will be accessible at:
# - https://your-site.com/api/method/farmlink.sync.pull_changes
# - https://your-site.com/api/method/farmlink.sync.push_changes
# - https://your-site.com/api/method/farmlink.sync.get_sync_status

# Whitelist API methods (already decorated with @frappe.whitelist() in the Python file)
# No additional configuration needed here for API endpoints

# Document Events (optional - for additional sync logic)
doc_events = {
    "Farmer": {
        "after_insert": "farmlink.sync.on_farmer_change",
        "on_update": "farmlink.sync.on_farmer_change",
        "on_trash": "farmlink.sync.on_farmer_change"
    },
    "Payment": {
        "after_insert": "farmlink.sync.on_payment_change",
        "on_update": "farmlink.sync.on_payment_change", 
        "on_trash": "farmlink.sync.on_payment_change"
    },
    "Purchase": {
        "after_insert": "farmlink.sync.on_purchase_change",
        "on_update": "farmlink.sync.on_purchase_change",
        "on_trash": "farmlink.sync.on_purchase_change"
    },
    "Territory": {
        "after_insert": "farmlink.sync.on_territory_change",
        "on_update": "farmlink.sync.on_territory_change",
        "on_trash": "farmlink.sync.on_territory_change"
    },
    "Washing Station": {
        "after_insert": "farmlink.sync.on_washing_station_change",
        "on_update": "farmlink.sync.on_washing_station_change",
        "on_trash": "farmlink.sync.on_washing_station_change"
    }
}

# Scheduled Tasks (optional - for periodic sync operations)
scheduler_events = {
    "daily": [
        "farmlink.sync.daily_sync_cleanup"
    ]
}

# Installation
# after_install = "farmlink.install.after_install"

# Desk Notifications
# notification_config = "farmlink.notifications.get_notification_config"

# Permissions
# permission_query_conditions = {
#     "Farmer": "farmlink.permissions.get_permission_query_conditions_for_farmer",
# }

# Authentication
# auth_hooks = [
#     "farmlink.auth.validate_auth"
# ]
