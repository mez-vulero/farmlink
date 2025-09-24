import frappe

@frappe.whitelist(allow_guest=False)
def get_current_user_roles():
    """
    Returns the roles of the currently logged-in or API-authenticated user.
    """
    user = frappe.session.user
    roles = frappe.get_roles(user)
    return roles

@frappe.whitelist(allow_guest=False)
def get_personnel_data():
    """
    Fetch all Personnel data for the currently authenticated user.
    """
    user = frappe.session.user

    # Find Personnel record linked to this user
    personnel_id = frappe.db.get_value("Personnel", {"user_id": user}, "name")

    if not personnel_id:
        return {"error": f"No Personnel record found for {user}"}

    # Load full Personnel document
    doc = frappe.get_doc("Personnel", personnel_id)

    # Return as dict (with all fields & children)
    return doc.as_dict()

