# apps/farmlink/farmlink/api.py
import json
import re
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
def get_farm_center_points(site=None):
    """Return farm geo points with collection site (territory), optionally filtered."""
    lat_lng_re = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")

    filters = {"farm_center_point": ["is", "set"]}
    if site:
        filters["territory"] = site

    rows = frappe.db.get_all(
        "Farms",
        fields=["name", "farm_center_point", "farmer", "territory"],
        filters=filters,
    )

    points = []
    for row in rows:
        val = row.farm_center_point
        if not val:
            continue
        try:
            obj = None
            if isinstance(val, dict):
                obj = val
            else:
                try:
                    obj = json.loads(val)
                except Exception:
                    pass

            lat = lng = None
            if obj:
                lat = obj.get("lat") or obj.get("latitude")
                lng = obj.get("lng") or obj.get("longitude")
                if lat is None and obj.get("type") == "FeatureCollection":
                    for feat in (obj.get("features") or []):
                        geom = feat.get("geometry") or {}
                        if geom.get("type") == "Point":
                            coords = geom.get("coordinates") or []
                            if len(coords) >= 2:
                                lng, lat = coords[0], coords[1]
                                break
            elif isinstance(val, str):
                m = lat_lng_re.match(val)
                if m:
                    lat, lng = m.group(1), m.group(2)

            if lat is not None and lng is not None:
                points.append({
                    "name": row.name,
                    "lat": float(lat),
                    "lng": float(lng),
                    "site": row.territory or "",
                    "farmer": row.farmer or "",
                })
        except Exception:
            continue

    # Get all Territory records for the filter dropdown
    all_territories = frappe.db.get_all("Territory", fields=["name"], order_by="name asc")
    sites = [t.name for t in all_territories]
    return {"points": points, "sites": sites}


@frappe.whitelist()
def get_farm_area_by_site(site=None):
    """Return total coffee farm area (hectares) grouped by collection site (territory)."""
    filters = {"territory": ["is", "set"]}
    if site:
        filters["territory"] = site

    rows = frappe.db.get_all(
        "Farmers",
        fields=["territory as site", "land_size_allocated_for_coffee_in_hectares as area"],
        filters=filters,
    )

    totals = {}
    for r in rows:
        totals[r.site] = totals.get(r.site, 0) + (r.area or 0)

    data = [{"site": k, "area": round(v, 2)} for k, v in sorted(totals.items())]

    # All available territory options for the filter
    all_territories = frappe.db.get_all("Territory", fields=["name"], order_by="name asc")
    sites = [t.name for t in all_territories]
    return {"data": data, "sites": sites}
