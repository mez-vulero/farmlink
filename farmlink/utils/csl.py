# utils/csl.py
import frappe
from frappe.utils import now_datetime, flt

CSL = "Coffee Stock Ledger"

@frappe.whitelist()
def post_csl(*, center, status, form, qty, ref_dt, ref_dn, batch_ref=None, remarks="", cancelled=0):
    """
    Insert a Coffee Stock Ledger row.
    NOTE: CSL location field is named 'washing_station' and links to Centers.
    """
    doc = frappe.get_doc({
        "doctype": CSL,
        "posting_time": now_datetime(),
        "washing_station": center,   # Centers link (location)
        "status": status,            # Primary Arrival | In Processing | Dispatched to Secondary | Secondary Arrival
        "coffee_form": form,         # Cherry | Parchment | Dried Cherry | Green Bean
        "qty_kg": flt(qty),
        "reference_doctype": ref_dt,
        "reference_name": ref_dn,
        "remarks": remarks,
        "is_cancelled": cancelled,
        # New field you add to CSL:
        "batch_ref": batch_ref       # Link to Primary Processing (lot identity)
    })
    doc.insert(ignore_permissions=True)

@frappe.whitelist()
def sum_csl_qty(*, center, status, form, batch_ref=None, ref_dt=None, ref_dn=None):
    """
    Net qty in CSL with optional filters: by batch and/or specific reference doc.
    """
    bt_cond  = "AND batch_ref=%s" if batch_ref else ""
    ref_cond = "AND reference_doctype=%s AND reference_name=%s" if (ref_dt and ref_dn) else ""
    params = [center, status, form]
    if batch_ref: params.append(batch_ref)
    if ref_dt and ref_dn: params.extend([ref_dt, ref_dn])

    rows = frappe.db.sql(f"""
        SELECT COALESCE(SUM(qty_kg),0)
        FROM `tab{CSL}`
        WHERE is_cancelled=0
          AND washing_station=%s AND status=%s AND coffee_form=%s
          {bt_cond} {ref_cond}
    """, params)
    return flt(rows[0][0] if rows else 0)

@frappe.whitelist()
def get_center_type(center_name: str) -> str:
    return frappe.db.get_value("Centers", center_name, "type") or ""

@frappe.whitelist()
def center_total(*, center, status, form):
    rows = frappe.db.sql(f"""
        SELECT COALESCE(SUM(qty_kg),0)
        FROM `tab{CSL}`
        WHERE is_cancelled=0 AND washing_station=%s AND status=%s AND coffee_form=%s
    """, (center, status, form))
    return flt(rows[0][0] if rows else 0)
