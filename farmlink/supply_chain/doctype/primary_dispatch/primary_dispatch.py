# primary_dispatch.py
import frappe
from frappe.utils import flt
from farmlink.utils.csl import post_csl, sum_csl_qty, get_center_type

ROUTE_DIRECT_TO_MAIN = ("Parchment", "Green Bean")   # Washed → Parchment OR post-secondary → Green Bean
ROUTE_TO_SECONDARY   = ("Dried Cherry",)             # Natural path

def _validate_route(self):
    # Origin must be Temporary Warehouse
    if get_center_type(self.dispatched_from) != "Temporary Warehouse":
        frappe.throw("You can only dispatch from a Center of type <b>Temporary Warehouse</b>.")

    # Destination rules by coffee_type
    ctype = (self.coffee_type or "").strip()
    dest_type = get_center_type(self.destination)
    if ctype in ROUTE_DIRECT_TO_MAIN and dest_type != "Main Warehouse":
        frappe.throw(f"Dispatch Type {ctype} must go to a Center of type <b>Main Warehouse</b>.")
    if ctype in ROUTE_TO_SECONDARY and dest_type != "Washing Station":
        frappe.throw("Dried Cherry must go to a Center of type <b>Washing Station</b> (secondary processing site).")

def validate(self):
    if not self.dispatched_from or not self.destination:
        frappe.throw("Please set <b>Dispatched From</b> and <b>Destination</b> centers.")
    if not self.coffee_type:
        frappe.throw("Set the <b>Dispatch Type</b> (Parchment / Dried Cherry / Green Bean).")  # field exists on PD. :contentReference[oaicite:8]{index=8}
    if (self.status or "").lower() != "dispatched":
        return  # postings happen only on submit, but we validate structure regardless

    _validate_route(self)

    lines = self.get("batches") or []
    if not lines:
        frappe.throw("Add at least one <b>batch line</b> (Primary Dispatch Batch).")

    # Header weight must match sum of lines (or we auto-set if header is empty)
    total_lines = sum(flt(r.qty_kg or 0) for r in lines)
    if flt(self.weight_in_kg or 0) <= 0:
        self.db_set("weight_in_kg", total_lines)  # PD header field exists. :contentReference[oaicite:9]{index=9}
    elif abs(flt(self.weight_in_kg) - total_lines) > 1e-6:
        frappe.throw(f"Header Weight in KG ({self.weight_in_kg}) must equal the sum of batch lines ({total_lines}).")

    # Each batch must have sufficient on-hand in origin (Primary Arrival / coffee_type / batch_ref)
    for r in lines:
        if not r.pp_ref:
            frappe.throw("Each batch line must set <b>PP Batch</b>.")
        available = sum_csl_qty(center=self.dispatched_from, status="Primary Arrival",
                                form=self.coffee_type, batch_ref=r.pp_ref)
        if flt(r.qty_kg or 0) > available:
            frappe.throw(
                f"Not enough {self.coffee_type} for batch {r.pp_ref} at {self.dispatched_from}. "
                f"Available: {available} kg."
            )

def on_submit(self):
    if (self.status or "").lower() != "dispatched":
        return

    # Choose the in-transit status by route
    ctype = (self.coffee_type or "").strip()
    in_transit_status = "Dispatched to Main" if ctype in ROUTE_DIRECT_TO_MAIN else "Dispatched to Secondary"

    # Post per batch line
    for r in self.get("batches") or []:
        qty = flt(r.qty_kg or 0)
        if qty <= 0: 
            continue
        # OUT: on-hand @ origin (Primary Arrival)
        post_csl(center=self.dispatched_from, status="Primary Arrival", form=self.coffee_type,
                 qty=-qty, ref_dt=self.doctype, ref_dn=self.name, batch_ref=r.pp_ref,
                 remarks=f"Dispatch out (batch {r.pp_ref})")
        # IN-TRANSIT @ origin (route-dependent)
        post_csl(center=self.dispatched_from, status=in_transit_status, form=self.coffee_type,
                 qty=+qty, ref_dt=self.doctype, ref_dn=self.name, batch_ref=r.pp_ref,
                 remarks=f"In transit ({in_transit_status}) batch {r.pp_ref}")

def on_cancel(self):
    ctype = (self.coffee_type or "").strip()
    in_transit_status = "Dispatched to Main" if ctype in ROUTE_DIRECT_TO_MAIN else "Dispatched to Secondary"

    for r in self.get("batches") or []:
        qty = flt(r.qty_kg or 0)
        if qty <= 0:
            continue
        # Reverse OUT
        post_csl(center=self.dispatched_from, status="Primary Arrival", form=self.coffee_type,
                 qty=+qty, ref_dt=self.doctype, ref_dn=self.name, batch_ref=r.pp_ref,
                 remarks=f"Cancel PD: return on-hand (batch {r.pp_ref})", cancelled=1)
        # Reverse IN-TRANSIT
        post_csl(center=self.dispatched_from, status=in_transit_status, form=self.coffee_type,
                 qty=-qty, ref_dt=self.doctype, ref_dn=self.name, batch_ref=r.pp_ref,
                 remarks=f"Cancel PD: reverse transit (batch {r.pp_ref})", cancelled=1)
