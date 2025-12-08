# apps/farmlink/farmlink/api.py
import json
import frappe


def _sum_active_payments(purchase_name: str) -> float:
    """Sum payments linked to a purchase (draft or submitted, ignore cancelled)."""
    rows = frappe.db.get_all(
        "Payment",
        filters={"purchase_invoice": purchase_name, "docstatus": ["!=", 2]},
        fields=["payment_amount"],
    )
    return sum((r.payment_amount or 0) for r in rows)

@frappe.whitelist()
def get_payment_summary(purchase_name: str) -> dict:
    """Return totals used by the Purchases form."""
    pur = frappe.get_doc("Purchases", purchase_name)
    total = float(pur.get("total_price") or 0.0)
    paid = _sum_active_payments(purchase_name)
    outstanding = max(total - paid, 0.0)

    if paid <= 0:
        status = "Unpaid"
    elif outstanding > 0:
        status = "Partially Paid"
    else:
        status = "Paid"

    return {"total": total, "paid": paid, "outstanding": outstanding, "status": status}

@frappe.whitelist()
def make_payment_from_purchase(purchase_name: str) -> str:
    """Create a Payment linked to the Purchase. Returns new Payment name."""
    summary = get_payment_summary(purchase_name)
    if summary["outstanding"] <= 0:
        frappe.throw("This Purchase is already fully paid.")

    p = frappe.new_doc("Payment")
    p.purchase_invoice = purchase_name            # Link to Purchases
    # Set defaults as you like:
    # p.payment_amount = summary["outstanding"]   # or leave for user to type
    p.insert()                                    # will run validations
    return p.name

@frappe.whitelist()
def _write_purchase_summary(purchase_name: str):
    summary = get_payment_summary(purchase_name)
    updates = {}
    if frappe.db.has_column("Purchases", "outstanding_amount"):
        updates["outstanding_amount"] = summary["outstanding"]
    if frappe.db.has_column("Purchases", "status"):  # or purchase_status
        updates["status"] = summary["status"]
    if updates:
        frappe.db.set_value("Purchases", purchase_name, updates)


@frappe.whitelist()
def get_farm_center_points():
    """Return list of geo points for farm_center_point (lat/lng)."""
    points = []
    rows = frappe.db.get_all(
        "Farms",
        fields=["name", "farm_center_point"],
        filters={"farm_center_point": ["is", "set"]},
    )
    for row in rows:
        val = row.farm_center_point
        if not val:
            continue
        try:
            obj = val if isinstance(val, dict) else json.loads(val)
            lat = obj.get("lat") or obj.get("latitude")
            lng = obj.get("lng") or obj.get("longitude")
            if lat is not None and lng is not None:
                points.append({"name": row.name, "lat": float(lat), "lng": float(lng)})
        except Exception:
            # ignore malformed values
            continue
    return points
