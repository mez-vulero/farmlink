import frappe
import json


def execute():
    """Update FarmLink workspace: rename chart label, remove shortcut counts."""
    if not frappe.db.exists("Workspace", "FarmLink"):
        return

    ws = frappe.get_doc("Workspace", "FarmLink")

    # 1. Rename "Farmers by Territory" chart display to "Farmers by Site"
    content = json.loads(ws.content or "[]")
    for item in content:
        if (
            item.get("type") == "chart"
            and item.get("data", {}).get("chart_name") == "Farmers by Territory"
        ):
            item["data"]["chart_name"] = "Farmers by Site"
    ws.content = json.dumps(content)

    for c in ws.charts:
        if c.chart_name == "Farmers by Territory":
            c.chart_name = "Farmers by Site"
            c.label = "Farmers by Site"

    # 2. Remove count badges from shortcuts
    for s in ws.shortcuts:
        s.stats_filter = None

    ws.flags.ignore_links = True
    ws.save(ignore_permissions=True)
    frappe.db.commit()

    # 3. Rename the Dashboard Chart document itself so title matches
    if frappe.db.exists("Dashboard Chart", "Farmers by Territory"):
        if not frappe.db.exists("Dashboard Chart", "Farmers by Site"):
            frappe.rename_doc(
                "Dashboard Chart", "Farmers by Territory", "Farmers by Site", force=True
            )
            frappe.db.commit()
