import frappe

def boot_session(bootinfo):
    key = frappe.db.get_single_value("Google Settings", "api_key")
    if key:
        bootinfo["google_maps_api_key"] = key
