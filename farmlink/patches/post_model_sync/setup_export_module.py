import frappe


def execute():
    """Set up export module: create Export Officer role, default existing Trades to Draft."""
    # Create Export Officer role if it doesn't exist
    if not frappe.db.exists("Role", "Export Officer"):
        role = frappe.new_doc("Role")
        role.role_name = "Export Officer"
        role.desk_access = 1
        role.insert(ignore_permissions=True)
        frappe.db.commit()

    # Set status=Draft on any existing Trades that don't have a status
    frappe.db.sql("""
        UPDATE `tabTrades`
        SET status = 'Draft'
        WHERE status IS NULL OR status = ''
    """)
    frappe.db.commit()
