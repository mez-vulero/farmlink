# Copyright (c) 2025, vulerotech and contributors
# For license information, please see license.txt

# secondary_processing.py
import frappe
from frappe.model.document import Document
from frappe.utils import flt, now_datetime
from farmlink.utils.csl import post_csl, sum_csl_qty, get_center_type

INPUT_FORM  = "Dried Cherry"
OUTPUT_FORM = "Green Bean"

class SecondaryProcessing(Document):
    """
    Secondary Processing converts pooled Dried Cherry (arrived to a Washing Station)
    into Green Bean stored at a Temporary Warehouse.

    Batch identity for this stage = document name (naming series). We DO NOT carry pp_ref;
    input stock is considered pooled across arrivals. We therefore:
      - consume INPUT_FORM from pooled 'Secondary Arrival' @ processing_center (no batch_ref filter)
      - create WIP tagged with batch_ref=self.name
      - on completion, create OUTPUT_FORM on-hand @ processed_center tagged with batch_ref=self.name
    """

    # ------- Validation -------
    def validate(self):
        if flt(self.weight_in_kg or 0) <= 0:
            frappe.throw("Weight in KG must be > 0.")

        if not self.processing_center:
            frappe.throw("Please set <b>Processing Center</b> (Centers).")
        if get_center_type(self.processing_center) != "Washing Station":
            frappe.throw("Processing Center must be of type <b>Washing Station</b>.")

        # When completing, finished beans must be stored in a Temporary Warehouse
        if (self.status or "").lower() == "completed":
            if not self.processed_center:
                frappe.throw("Please set <b>Processed Center</b> (Temporary Warehouse) before completing.")
            if get_center_type(self.processed_center) != "Temporary Warehouse":
                frappe.throw("Processed Center must be of type <b>Temporary Warehouse</b>.")

    # ------- Draft-time postings -------
    def on_save(self):
        """
        Keep CSL in sync while draft:
          • Move Dried Cherry from pooled on-hand (Secondary Arrival) → In Processing to match weight_in_kg.
          • If status == Completed, consume WIP and add finished Green Bean to on-hand at processed_center.
        """
        self._reconcile_wip_from_pool()
        self._post_conversion_if_completed()

    def _reconcile_wip_from_pool(self):
        """
        Align WIP = weight_in_kg at the processing_center by moving delta between:
          - on-hand pooled INPUT_FORM:   (status='Secondary Arrival',  batch_ref=IGNORED)
          - WIP tagged to this SP doc:   (status='In Processing',       batch_ref=self.name)
        """
        target = flt(self.weight_in_kg)
        posted_wip = sum_csl_qty(
            center=self.processing_center,
            status="In Processing",
            form=INPUT_FORM,
            ref_dt=self.doctype, ref_dn=self.name   # limit to this SP's WIP
        )
        delta = target - posted_wip
        if abs(delta) < 1e-9:
            return

        if delta > 0:
            # Need more WIP → must exist as pooled on-hand at processing_center (no batch_ref filter)
            pooled_onhand = sum_csl_qty(
                center=self.processing_center,
                status="Secondary Arrival",
                form=INPUT_FORM
            )
            if delta > pooled_onhand:
                frappe.throw(
                    f"Not enough {INPUT_FORM} at {self.processing_center} (pooled). "
                    f"Available: {pooled_onhand} kg, Needed: {delta} kg."
                )
            # Consume pooled on-hand (no batch_ref), create WIP tagged to this SP batch_ref
            post_csl(center=self.processing_center, status="Secondary Arrival", form=INPUT_FORM,
                     qty=-delta, ref_dt=self.doctype, ref_dn=self.name,
                     batch_ref=None, remarks="Move to WIP (delta)")
            post_csl(center=self.processing_center, status="In Processing", form=INPUT_FORM,
                     qty=+delta, ref_dt=self.doctype, ref_dn=self.name,
                     batch_ref=self.name, remarks="WIP allocation (delta)")
        else:
            # Over-allocated → return excess from WIP to pooled on-hand
            excess = -delta
            post_csl(center=self.processing_center, status="Secondary Arrival", form=INPUT_FORM,
                     qty=+excess, ref_dt=self.doctype, ref_dn=self.name,
                     batch_ref=None, remarks="Return from WIP (delta)")
            post_csl(center=self.processing_center, status="In Processing", form=INPUT_FORM,
                     qty=-excess, ref_dt=self.doctype, ref_dn=self.name,
                     batch_ref=self.name, remarks="Reduce WIP (delta)")

    def _post_conversion_if_completed(self):
        """
        When Completed (still draft):
          1) consume any remaining WIP INPUT_FORM for THIS SP (tagged batch_ref=self.name)
          2) create OUTPUT_FORM on-hand @ processed_center (status='Primary Arrival'), batch_ref=self.name
             using final_output_weight_kg (fallback to input weight if empty)
        """
        if (self.status or "").lower() != "completed":
            return

        # 1) consume remaining WIP FOR THIS SP only
        wip_net = sum_csl_qty(
            center=self.processing_center,
            status="In Processing",
            form=INPUT_FORM,
            ref_dt=self.doctype, ref_dn=self.name
        )
        if wip_net > 0:
            post_csl(center=self.processing_center, status="In Processing", form=INPUT_FORM,
                     qty=-wip_net, ref_dt=self.doctype, ref_dn=self.name,
                     batch_ref=self.name, remarks="WIP consumed (Completed)")

        # 2) produce finished OUTPUT_FORM on-hand at processed_center
        produced = flt(getattr(self, "final_output_weight_kg", self.weight_in_kg))
        already  = sum_csl_qty(center=self.processed_center, status="Primary Arrival",
                               form=OUTPUT_FORM, ref_dt=self.doctype, ref_dn=self.name)
        delta = produced - already
        if abs(delta) > 1e-9:
            post_csl(center=self.processed_center, status="Primary Arrival", form=OUTPUT_FORM,
                     qty=delta, ref_dt=self.doctype, ref_dn=self.name,
                     batch_ref=self.name, remarks="Secondary processing completed → Processed Center")

    # ------- Submit / Cancel -------
    def before_submit(self):
        if (self.status or "").lower() != "completed":
            frappe.throw("You can only submit when Status is set to <b>Completed</b>.")

    def on_submit(self):
        # on_save already posted; submit is side-effect free
        pass

    def on_cancel(self):
        """
        Reverse this document's postings:
          - reverse any WIP tagged to this SP
          - reverse finished OUTPUT_FORM at processed_center (tagged to this SP)
          - return INPUT_FORM taken from pooled on-hand back into pooled on-hand
        """
        # Reverse remaining WIP FOR THIS SP
        wip_net = sum_csl_qty(center=self.processing_center, status="In Processing",
                              form=INPUT_FORM, ref_dt=self.doctype, ref_dn=self.name)
        if abs(wip_net) > 1e-9:
            post_csl(center=self.processing_center, status="In Processing", form=INPUT_FORM,
                     qty=-wip_net, ref_dt=self.doctype, ref_dn=self.name,
                     batch_ref=self.name, remarks="Cancel SP: reverse WIP", cancelled=1)

        # Reverse finished OUTPUT_FORM posted by THIS SP
        fin_net = sum_csl_qty(center=self.processed_center, status="Primary Arrival",
                              form=OUTPUT_FORM, ref_dt=self.doctype, ref_dn=self.name)
        if abs(fin_net) > 1e-9:
            post_csl(center=self.processed_center, status="Primary Arrival", form=OUTPUT_FORM,
                     qty=-fin_net, ref_dt=self.doctype, ref_dn=self.name,
                     batch_ref=self.name, remarks="Cancel SP: reverse finished", cancelled=1)

        # Return pooled INPUT_FORM consumed by THIS SP back to pooled on-hand
        consumed_net = sum_csl_qty(center=self.processing_center, status="Secondary Arrival",
                                   form=INPUT_FORM, ref_dt=self.doctype, ref_dn=self.name)
        # consumed_net will be negative if we pulled from pooled on-hand; add back its absolute value
        if consumed_net < 0:
            post_csl(center=self.processing_center, status="Secondary Arrival", form=INPUT_FORM,
                     qty=+(-consumed_net), ref_dt=self.doctype, ref_dn=self.name,
                     batch_ref=None, remarks="Cancel SP: return pooled on-hand", cancelled=1)

    # ------- Draft delete safety -------
    def on_trash(self):
        """
        Delete while draft:
          - prevent negative buckets by simulating removal of this doc's CSL rows
          - if safe, delete all CSL rows tied to this doc (reference_doctype/name)
        """
        if self.docstatus != 0:
            return

        rows = frappe.db.sql("""
            SELECT washing_station AS center, status, coffee_form, COALESCE(SUM(qty_kg),0) AS net_qty
            FROM `tabCoffee Stock Ledger`
            WHERE is_cancelled=0 AND reference_doctype=%s AND reference_name=%s
            GROUP BY washing_station, status, coffee_form
        """, (self.doctype, self.name), as_dict=True)

        for r in rows or []:
            total_now = frappe.db.sql("""
                SELECT COALESCE(SUM(qty_kg),0)
                FROM `tabCoffee Stock Ledger`
                WHERE is_cancelled=0 AND washing_station=%s AND status=%s AND coffee_form=%s
            """, (r.center, r.status, r.coffee_form))[0][0]
            if (total_now - flt(r.net_qty)) < -1e-9:
                frappe.throw(
                    f"Cannot delete this draft Secondary Processing: removing its CSL entries would make "
                    f"[{r.center} / {r.status} / {r.coffee_form}] negative."
                )

        # Safe to delete: wipe all CSL rows referencing this SP
        frappe.db.delete("Coffee Stock Ledger", {
            "reference_doctype": self.doctype, "reference_name": self.name
        })
