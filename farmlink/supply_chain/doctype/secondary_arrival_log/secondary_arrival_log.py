# Copyright (c) 2025, vulerotech and contributors
# For license information, please see license.txt

# secondary_arrival_log.py
import frappe
from frappe.utils import flt
from farmlink.utils.csl import post_csl, get_center_type

def _arrival_status_and_required_center_type(pd_coffee_type: str):
    ctype = (pd_coffee_type or "").strip()
    if ctype in ("Parchment", "Green Bean"):
        return ("Main Arrival", "Main Warehouse")
    if ctype == "Dried Cherry":
        return ("Secondary Arrival", "Washing Station")
    frappe.throw(f"Unsupported Dispatch Type on PD: {ctype}")

def on_submit(self):
    pd = frappe.get_doc("Primary Dispatch", self.dispatch_log)  # SAL → PD link exists. :contentReference[oaicite:12]{index=12}
    lines = pd.get("batches") or []

    arrival_status, required_center_type = _arrival_status_and_required_center_type(pd.coffee_type)

    # Validate the arrival center type for the route
    if get_center_type(self.arrival_center) != required_center_type:
        frappe.throw(
            f"Arrival Center must be a <b>{required_center_type}</b> for {pd.coffee_type} shipments."
        )

    # Determine arrived quantity (handles partial arrivals)
    dispatched_total = flt(self.dispatched_weight_in_kg or 0)
    if dispatched_total <= 0:
        dispatched_total = sum(flt(r.qty_kg or 0) for r in lines)
    missing = flt(self.quantity_missing_in_weightkg or 0) if self.delivery_status == "Partially Arrived" else 0
    arrived_total = max(0, dispatched_total - missing)

    if not lines:
        # Fallback (shouldn’t happen with our PD), no batch split
        if arrived_total > 0:
            post_csl(center=self.arrival_center, status=arrival_status, form=pd.coffee_type,
                     qty=arrived_total, ref_dt=self.doctype, ref_dn=self.name,
                     remarks=f"{arrival_status} (no batch detail)")
        return

    # Allocate arrived qty proportionally to PD batch lines
    line_sum = sum(flt(r.qty_kg or 0) for r in lines) or 1.0
    remaining = arrived_total
    for i, r in enumerate(lines, 1):
        dispatched_i = flt(r.qty_kg or 0)
        if i < len(lines):
            arrived_i = round(arrived_total * (dispatched_i / line_sum), 3)
            remaining -= arrived_i
        else:
            arrived_i = max(0, round(remaining, 3))  # last line = remainder
        if arrived_i > 0:
            post_csl(center=self.arrival_center, status=arrival_status, form=pd.coffee_type,
                     qty=arrived_i, ref_dt=self.doctype, ref_dn=self.name, batch_ref=r.pp_ref,
                     remarks=f"{arrival_status} (batch {r.pp_ref})")

def on_cancel(self):
    # Reverse exactly what this SAL posted (robust even with proration)
    # We don’t need the PD to reverse; just query rows tied to this SAL.
    rows = frappe.db.sql("""
        SELECT washing_station, status, coffee_form, batch_ref, COALESCE(SUM(qty_kg),0) AS qty
        FROM `tabCoffee Stock Ledger`
        WHERE is_cancelled=0 AND reference_doctype=%s AND reference_name=%s
        GROUP BY washing_station, status, coffee_form, batch_ref
    """, (self.doctype, self.name), as_dict=True)

    for r in rows or []:
        if flt(r.qty) <= 0:
            continue
        post_csl(center=r.washing_station, status=r.status, form=r.coffee_form,
                 qty=-flt(r.qty), ref_dt=self.doctype, ref_dn=self.name, batch_ref=r.batch_ref,
                 remarks="Cancel SAL: reverse arrival", cancelled=1)

