import frappe


def execute():
    """Force-refresh the FarmLink workspace from the fixture JSON.

    The workspace is cached in the database and doesn't auto-update when
    the fixture file changes. Deleting it lets Frappe recreate it from
    the latest JSON during migrate.
    """
    if frappe.db.exists("Workspace", "FarmLink"):
        frappe.delete_doc("Workspace", "FarmLink", force=True)
        frappe.db.commit()
