import frappe
from frappe.model.document import Document
from frappe.utils import flt, now_datetime, time_diff_in_hours

CSL = "Coffee Stock Ledger"

WASHED_TEMPLATE = [
    "Pulping",
    "Fermentation",       # track fermentation_mode + elapsed_hours
    "Washing",            # track multiple washing_tank_id rows in child table
    "Socking",            # soaking step (as per your spelling)
    "Drying",             # track multiple drying_bed_id rows in child table
    "Stored",             # capture final moisture + final_output_weight_kg → update CSL
]

NATURAL_TEMPLATE = [
    "Pulping",
    "Drying",
    "Stored",
]

FINISHED_FORM_BY_TYPE = {
    "Washed": "Parchment",
    "Natural": "Dried Cherry",
}

# ------------------- Centers helpers -------------------

def get_center_type(center_name: str) -> str:
    return frappe.db.get_value("Centers", center_name, "type") or ""

# ------------------- CSL helpers -------------------

def post_csl(*, station, status, form, qty, ref_dt, ref_dn, remarks="", cancelled=0, batch_ref=None):
    """Insert a CSL row. NOTE: 'washing_station' links to Centers."""
    doc = frappe.get_doc({
        "doctype": CSL,
        "posting_time": now_datetime(),
        "washing_station": station,   # Centers link (location)
        "status": status,             # Primary Arrival | In Processing | Dispatched to Secondary | Secondary Arrival
        "coffee_form": form,          # Cherry | Parchment | Dried Cherry | Green Bean
        "qty_kg": flt(qty),
        "reference_doctype": ref_dt,
        "reference_name": ref_dn,
        "remarks": remarks,
        "is_cancelled": cancelled,
        # NEW: lot identity = PP docname
        "batch_ref": batch_ref
    })
    doc.insert(ignore_permissions=True)

def sum_csl_qty_for_pp(*, ref_dt, ref_dn, station, status, form, sign=None):
    """Sum qty_kg for this PP in a given CSL bucket; sign: None|'pos'|'neg'."""
    cond = ""
    if sign == "pos":
        cond = "AND qty_kg > 0"
    elif sign == "neg":
        cond = "AND qty_kg < 0"
    val = frappe.db.sql(f"""
        SELECT COALESCE(SUM(qty_kg),0)
        FROM `tab{CSL}`
        WHERE is_cancelled=0
          AND reference_doctype=%s AND reference_name=%s
          AND washing_station=%s AND status=%s AND coffee_form=%s {cond}
    """, (ref_dt, ref_dn, station, status, form))
    return flt(val[0][0] if val else 0)

def sum_bucket_total(*, station, status, form):
    """Net total in a center bucket (across all refs)."""
    val = frappe.db.sql(f"""
        SELECT COALESCE(SUM(qty_kg),0)
        FROM `tab{CSL}`
        WHERE is_cancelled=0 AND washing_station=%s AND status=%s AND coffee_form=%s
    """, (station, status, form))
    return flt(val[0][0] if val else 0)

def available_onhand_cherry(station):
    """Cherry on-hand = Primary Arrival / Cherry at a Center."""
    return sum_bucket_total(station=station, status="Primary Arrival", form="Cherry")

# ------------------- Stage template helpers -------------------

def expected_template(processing_type: str):
    return WASHED_TEMPLATE if (processing_type or "").lower() == "washed" else NATURAL_TEMPLATE

def rows_match_template(rows, template):
    """Loose check: same ordered list of stage names."""
    names = [r.stage for r in rows] if rows else []
    return names == template

def safe_to_reapply_template(rows):
    """Allow reapply if no row has progressed beyond 'Not Started'."""
    if not rows:
        return True
    return all((getattr(r, "status", "Not Started") or "Not Started") == "Not Started" for r in rows)

def apply_stage_template(doc):
    """Ensure the stage template exists and matches processing_type (idempotent)."""
    tpl = expected_template(doc.processing_type)
    rows = doc.get("stage_logs") or []

    # If no rows, build fresh
    if not rows:
        for i, stage_name in enumerate(tpl, 1):
            doc.append("stage_logs", {"seq": i, "stage": stage_name, "status": "Not Started"})
        return

    # If rows exist but don't match, and no progress yet, rebuild
    if not rows_match_template(rows, tpl) and safe_to_reapply_template(rows):
        # clear and rebuild
        doc.set("stage_logs", [])
        for i, stage_name in enumerate(tpl, 1):
            doc.append("stage_logs", {"seq": i, "stage": stage_name, "status": "Not Started"})

def update_fermentation_elapsed_hours(doc):
    """Compute elapsed_hours for Fermentation when start/end are set."""
    for row in doc.get("stage_logs") or []:
        if (row.stage or "").lower() == "fermentation":
            st = getattr(row, "start_time", None)
            et = getattr(row, "end_time", None)
            if st and et:
                row.elapsed_hours = flt(time_diff_in_hours(et, st))

def require_resources_for_done_stages(doc):
    """
    If Washing or Drying are marked Done, ensure corresponding usage rows exist.
    Supports (optional) child mapping via stage_seq; falls back to any rows present.
    """
    tanks = doc.get("washing_tanks_used") or []
    beds = doc.get("drying_beds_used") or []

    for row in doc.get("stage_logs") or []:
        if (row.status or "").lower() != "done":
            continue
        if (row.stage or "").lower() == "washing":
            if tanks:
                has_for_stage = any(getattr(t, "stage_seq", None) in (None, row.seq) for t in tanks)
                if not has_for_stage:
                    frappe.throw("Please record at least one Washing Tank usage for the Washing stage.")
            else:
                frappe.throw("Please record Washing Tank usage before marking Washing as Done.")
        if (row.stage or "").lower() == "drying":
            if beds:
                has_for_stage = any(getattr(b, "stage_seq", None) in (None, row.seq) for b in beds)
                if not has_for_stage:
                    frappe.throw("Please record at least one Drying Bed usage for the Drying stage.")
            else:
                frappe.throw("Please record Drying Bed usage before marking Drying as Done.")

# ------------------- WIP & conversion reconciliations -------------------

def reconcile_wip_allocation(doc):
    """
    Keep WIP aligned to doc.weight_in_kg while draft:
    move delta between Primary Arrival/Cherry and In Processing/Cherry buckets,
    referenced to this PP, within the *processing_center*.
    """
    if not getattr(doc, "processing_center", None):
        return  # validated elsewhere

    target = flt(doc.weight_in_kg)
    posted_wip = sum_csl_qty_for_pp(
        ref_dt=doc.doctype, ref_dn=doc.name, station=doc.processing_center,
        status="In Processing", form="Cherry"
    )
    delta = target - posted_wip
    if abs(delta) < 1e-9:
        return

    if delta > 0:
        # Need to allocate more WIP — check on-hand Cherry at processing_center
        onhand = available_onhand_cherry(doc.processing_center)
        if delta > onhand:
            frappe.throw(
                f"Not enough Cherry at {doc.processing_center} to move to WIP. "
                f"Available: {onhand} kg, Needed: {delta} kg."
            )
        post_csl(
            station=doc.processing_center, status="Primary Arrival", form="Cherry",
            qty=-delta, ref_dt=doc.doctype, ref_dn=doc.name,
            remarks="Move to WIP (delta)", batch_ref=doc.name
        )
        post_csl(
            station=doc.processing_center, status="In Processing", form="Cherry",
            qty=+delta, ref_dt=doc.doctype, ref_dn=doc.name,
            remarks="WIP allocation (delta)", batch_ref=doc.name
        )
    else:
        # Over-allocated WIP — put excess back to on-hand
        excess = -delta
        post_csl(
            station=doc.processing_center, status="Primary Arrival", form="Cherry",
            qty=+excess, ref_dt=doc.doctype, ref_dn=doc.name,
            remarks="Return from WIP (delta)", batch_ref=doc.name
        )
        post_csl(
            station=doc.processing_center, status="In Processing", form="Cherry",
            qty=-excess, ref_dt=doc.doctype, ref_dn=doc.name,
            remarks="Reduce WIP (delta)", batch_ref=doc.name
        )

def post_conversion_if_completed(doc):
    """
    When status == Completed (still draft), consume remaining WIP at processing_center
    and add finished stock to on-hand at processed_center.
    Uses final_output_weight_kg if set; otherwise tries Stored.measured_weight_kg, else input weight.
    """
    if (doc.status or "").lower() != "completed":
        return
    if not getattr(doc, "processed_center", None):
        frappe.throw("Please set <b>Processed Center</b> (Temporary Warehouse) before completing.")

    # 1) Consume any remaining WIP Cherry for this PP (at processing_center)
    wip_net = sum_csl_qty_for_pp(
        ref_dt=doc.doctype, ref_dn=doc.name, station=doc.processing_center,
        status="In Processing", form="Cherry"
    )
    if wip_net > 0:
        post_csl(
            station=doc.processing_center, status="In Processing", form="Cherry",
            qty=-wip_net, ref_dt=doc.doctype, ref_dn=doc.name,
            remarks="WIP consumed (Completed)", batch_ref=doc.name
        )

    # 2) Determine finished form & quantity
    finished_form = FINISHED_FORM_BY_TYPE.get(doc.processing_type, "Parchment")
    final_weight = flt(getattr(doc, "final_output_weight_kg", 0) or 0)

    # fallback: try last Stored stage's measured_weight_kg if header field is empty
    if final_weight <= 0:
        for row in (doc.get("stage_logs") or [])[::-1]:
            if (row.stage or "").lower() == "stored":
                final_weight = flt(getattr(row, "measured_weight_kg", 0) or 0)
                if final_weight > 0:
                    break

    # Defensive: if still no final_weight, default to input (not ideal but prevents blockages)
    if final_weight <= 0:
        final_weight = flt(doc.weight_in_kg)

    # 3) Post finished stock (Primary Arrival bucket) at processed_center, batch-tagged
    posted_finished = sum_csl_qty_for_pp(
        ref_dt=doc.doctype, ref_dn=doc.name, station=doc.processed_center,
        status="Primary Arrival", form=finished_form
    )
    delta_finished = final_weight - posted_finished
    if abs(delta_finished) > 1e-9:
        post_csl(
            station=doc.processed_center, status="Primary Arrival", form=finished_form,
            qty=delta_finished, ref_dt=doc.doctype, ref_dn=doc.name,
            remarks="Processing completed → Processed Center", batch_ref=doc.name
        )

# ------------------- Safety / delete handling -------------------

def pp_bucket_summaries(doc):
    """All buckets (by center/status/form) this PP has touched (net)."""
    rows = frappe.db.sql(f"""
        SELECT washing_station AS center, status, coffee_form, COALESCE(SUM(qty_kg),0) AS net_qty
        FROM `tab{CSL}`
        WHERE is_cancelled=0 AND reference_doctype=%s AND reference_name=%s
        GROUP BY washing_station, status, coffee_form
    """, (doc.doctype, doc.name), as_dict=True)
    return rows or []

def cleanup_pp_csl_rows(doc):
    """Remove CSL rows for this PP (draft delete path)."""
    frappe.db.delete(CSL, {
        "reference_doctype": doc.doctype,
        "reference_name": doc.name
    })

# ------------------- The Document controller -------------------

class PrimaryProcessing(Document):

    # -------- Validation lifecycle --------
    def validate(self):
        # Required fields
        if flt(getattr(self, "weight_in_kg", 0)) <= 0:
            frappe.throw("Weight in KG must be > 0.")
        if not getattr(self, "processing_center", None):
            frappe.throw("Please set <b>Processing Center</b> (Centers).")

        # Center type checks
        if get_center_type(self.processing_center) != "Washing Station":
            frappe.throw("Processing Center must be of type <b>Washing Station</b>.")
        if (self.status or "").lower() == "completed":
            if not getattr(self, "processed_center", None):
                frappe.throw("Please set <b>Processed Center</b> (Temporary Warehouse) before completing.")
            if get_center_type(self.processed_center) != "Temporary Warehouse":
                frappe.throw("Processed Center must be of type <b>Temporary Warehouse</b>.")

        # Apply/repair the stage template if needed
        apply_stage_template(self)

        # Stage-specific computations & validations
        update_fermentation_elapsed_hours(self)
        require_resources_for_done_stages(self)

    # -------- Save lifecycle (draft postings) --------
    def on_save(self):
        """
        Keep CSL in sync while draft:
          • Move Cherry from on-hand (processing_center) → WIP to match weight_in_kg.
          • If status == Completed, consume WIP (processing_center) and add finished stock at processed_center.
        """
        reconcile_wip_allocation(self)
        post_conversion_if_completed(self)

    # -------- Submit / Cancel --------
    def before_submit(self):
        # Hard safety: never submit unless Completed
        if (self.status or "").lower() != "completed":
            frappe.throw("You can only submit when Status is set to <b>Completed</b>.")

    def on_submit(self):
        # CSL is already correct from on_save; keep submit side-effect free.
        pass

    def on_cancel(self):
        """
        If you ever cancel after submit, insert reversal rows (audit-friendly).
        """
        # Reverse remaining WIP (if any) at processing_center
        wip_net = sum_csl_qty_for_pp(
            ref_dt=self.doctype, ref_dn=self.name, station=self.processing_center,
            status="In Processing", form="Cherry"
        )
        if abs(wip_net) > 1e-9:
            post_csl(
                station=self.processing_center, status="In Processing", form="Cherry",
                qty=-wip_net, ref_dt=self.doctype, ref_dn=self.name,
                remarks="Cancel PP: reverse WIP", cancelled=1, batch_ref=self.name
            )

        # Reverse any finished stock posted at processed_center
        for form in ("Parchment", "Dried Cherry"):
            fin_net = sum_csl_qty_for_pp(
                ref_dt=self.doctype, ref_dn=self.name, station=self.processed_center,
                status="Primary Arrival", form=form
            )
            if abs(fin_net) > 1e-9:
                post_csl(
                    station=self.processed_center, status="Primary Arrival", form=form,
                    qty=-fin_net, ref_dt=self.doctype, ref_dn=self.name,
                    remarks="Cancel PP: reverse finished", cancelled=1, batch_ref=self.name
                )

        # Return on-hand Cherry taken by this PP (net) at processing_center
        cherry_net = sum_csl_qty_for_pp(
            ref_dt=self.doctype, ref_dn=self.name, station=self.processing_center,
            status="Primary Arrival", form="Cherry"
        )
        if cherry_net < 0:
            post_csl(
                station=self.processing_center, status="Primary Arrival", form="Cherry",
                qty=+(-cherry_net), ref_dt=self.doctype, ref_dn=self.name,
                remarks="Cancel PP: return on-hand", cancelled=1, batch_ref=self.name
            )

    # -------- Draft delete safety --------
    def on_trash(self):
        """
        Handle delete while draft:
          1) Prevent negative buckets if we removed this PP's CSL rows.
          2) If safe, clean up all CSL rows referencing this PP.
        """
        if self.docstatus != 0:
            # Submitted docs shouldn't be deleted
            return

        affected = pp_bucket_summaries(self)
        for b in affected:
            status, form, pp_net = b["status"], b["coffee_form"], flt(b["net_qty"])
            total_now = sum_bucket_total(station=b["center"], status=status, form=form)
            total_without_pp = total_now - pp_net
            if total_without_pp < -1e-9:
                frappe.throw(
                    f"Cannot delete this draft Primary Processing: removing its CSL entries would make "
                    f"[{status} / {form}] at {b['center']} go negative "
                    f"({total_without_pp:.3f} kg). Cancel downstream docs first (e.g., dispatches)."
                )

        # Safe: remove all CSL rows referencing this PP (or replace with reverse rows if you prefer)
        cleanup_pp_csl_rows(self)
