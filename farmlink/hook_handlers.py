import frappe
from farmlink.api import _write_purchase_summary

def on_payment_change(doc, method):
    if doc.get("purchase_invoice"):
        _write_purchase_summary(doc.purchase_invoice)


# Maps Personnel.designation values (free-text Select) to FarmLink custom Frappe Role names.
# Legacy designations (Collector, Arrival Clerk, Dispatcher, Export Clerk, Supplier) are
# folded into their nearest current role to preserve existing field deployments
# without forcing a data migration.
DESIGNATION_TO_ROLE = {
    "Area Manager": "FarmLink Area Manager",
    "Purchase and Finance": "FarmLink Purchase and Finance",
    "Collector": "FarmLink Purchase and Finance",
    "Supplier": "FarmLink Purchase and Finance",
    "Arrival and Processing": "FarmLink Arrival and Processing",
    "Arrival Clerk": "FarmLink Arrival and Processing",
    "Warehouse": "FarmLink Warehouse",
    "Dispatcher": "FarmLink Warehouse",
    "Export Clerk": "FarmLink Warehouse",
}

FARMLINK_ROLE_NAMES = frozenset(DESIGNATION_TO_ROLE.values())


def on_personnel_update(doc, method=None):
    """Sync Personnel.designation -> Frappe Role on the linked User.

    On every Personnel save, ensure the linked User has exactly the FarmLink role
    matching their designation, removing any other FarmLink role they previously
    carried. Non-FarmLink roles (System Manager, Farmlink Manager, etc.) are left
    untouched.
    """
    if not doc.get("user_id"):
        return

    target_role = DESIGNATION_TO_ROLE.get((doc.designation or "").strip())

    if not frappe.db.exists("User", doc.user_id):
        return

    user = frappe.get_doc("User", doc.user_id)

    user.roles = [
        r for r in user.roles
        if r.role not in FARMLINK_ROLE_NAMES or r.role == target_role
    ]

    existing = {r.role for r in user.roles}
    if target_role and target_role not in existing and frappe.db.exists("Role", target_role):
        user.append("roles", {"role": target_role})

    user.save(ignore_permissions=True)
