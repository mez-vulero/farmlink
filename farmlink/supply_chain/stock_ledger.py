# stock_ledger.py
import frappe
from frappe.utils import flt

from farmlink.utils.csl import record_transfer, reverse_entries


def _cancel_missing_entries(ref_dt, ref_dn, entry_type, keep_refs):
    """Cancel CSL rows for a doc/entry_type whose entry_ref is not in keep_refs."""
    existing = frappe.get_all(
        "Coffee Stock Ledger",
        filters={
            "reference_doctype": ref_dt,
            "reference_name": ref_dn,
            "entry_type": entry_type,
            "is_cancelled": 0,
        },
        fields=["name", "entry_ref"],
    )
    keep_refs = set(keep_refs)
    to_cancel = [row.name for row in existing if row.entry_ref not in keep_refs]
    for name in to_cancel:
        frappe.db.set_value("Coffee Stock Ledger", name, "is_cancelled", 1)


def primary_arrival_on_save(doc, method=None):
    qty = flt(doc.collected_weight)
    if not doc.center or qty <= 0:
        reverse_entries(doc.doctype, doc.name)
        return

    record_transfer(
        center=doc.center,
        status="Primary Arrival",
        form="Cherry",
        qty=qty,
        ref_dt=doc.doctype,
        ref_dn=doc.name,
        entry_type="IN",
        entry_ref="primary_arrival_in",
        remarks="Primary arrival of cherry",
    )


def primary_arrival_on_trash(doc, method=None):
    reverse_entries(doc.doctype, doc.name)


def _primary_output_form(processing_type):
    mapping = {
        "Washed": "Parchment",
        "Natural": "Dried Cherry",
        "Special Process": "Parchment",
    }
    return mapping.get(processing_type, "Parchment")


def primary_processing_on_save(doc, method=None):
    center = doc.processing_center
    status = (doc.status or "").strip()
    qty_in = flt(doc.weight_in_kg)

    if not center or status not in ("Processing", "Completed") or qty_in <= 0:
        reverse_entries(doc.doctype, doc.name)
        return

    # Consume cherry into processing
    record_transfer(
        center=center,
        status="In Processing",
        form="Cherry",
        qty=qty_in,
        ref_dt=doc.doctype,
        ref_dn=doc.name,
        entry_type="OUT",
        entry_ref="primary_proc_input",
        remarks="Primary processing input",
    )

    output_refs = []
    if status == "Completed":
        output_form = _primary_output_form(doc.processing_type)
        for idx, row in enumerate(doc.get("processing_output") or [], start=1):
            out_qty = flt(row.weightkg)
            entry_ref = f"primary_proc_output_{idx}"
            if out_qty <= 0:
                reverse_entries(doc.doctype, doc.name, entry_ref=entry_ref, entry_type="IN")
                continue

            record_transfer(
                center=center,
                status="In Processing",
                form=output_form,
                qty=out_qty,
                ref_dt=doc.doctype,
                ref_dn=doc.name,
                entry_type="IN",
                entry_ref=entry_ref,
                batch_ref=doc.name,
                coffee_grade=row.grade or None,
                remarks="Primary processing output",
            )
            output_refs.append(entry_ref)

    # Cancel any stale output entries if not in current output set
    _cancel_missing_entries(doc.doctype, doc.name, "IN", output_refs)


def primary_processing_on_trash(doc, method=None):
    reverse_entries(doc.doctype, doc.name)


def primary_dispatch_on_save(doc, method=None):
    status = (doc.status or "").strip()
    qty = flt(doc.weight_in_kg)
    coffee_form = (doc.coffee_type or "").strip()

    if status != "Dispatched" or qty <= 0 or not doc.dispatched_from:
        reverse_entries(doc.doctype, doc.name)
        return

    record_transfer(
        center=doc.dispatched_from,
        status="Dispatched",
        form=coffee_form,
        qty=qty,
        ref_dt=doc.doctype,
        ref_dn=doc.name,
        entry_type="OUT",
        entry_ref="primary_dispatch_out",
        to_center=doc.destination,
        coffee_grade=getattr(doc, "coffee_grade", None),
        remarks=f"Dispatched to {doc.destination or ''}",
    )


def primary_dispatch_on_trash(doc, method=None):
    reverse_entries(doc.doctype, doc.name)


def secondary_arrival_on_save(doc, method=None):
    if not doc.arrival_center:
        reverse_entries(doc.doctype, doc.name)
        return

    delivery_status = (doc.delivery_status or "").strip()
    dispatched_qty = flt(doc.dispatched_weight_in_kg)
    missing = flt(doc.quantity_missing_in_weightkg) if delivery_status == "Partially Arrived" else 0
    if delivery_status == "Wrong Delivery":
        dispatched_qty = 0
    qty_in = max(dispatched_qty - missing, 0)

    if qty_in <= 0:
        reverse_entries(doc.doctype, doc.name)
        return

    coffee_form = (doc.coffee_type or "").strip()
    from_center = getattr(doc, "source_center", None)

    # Try to grab grade from dispatch log if available
    coffee_grade = None
    if getattr(doc, "dispatch_log", None):
        coffee_grade = frappe.db.get_value("Primary Dispatch", doc.dispatch_log, "coffee_grade")

    record_transfer(
        center=doc.arrival_center,
        status="Secondary Arrival",
        form=coffee_form,
        qty=qty_in,
        ref_dt=doc.doctype,
        ref_dn=doc.name,
        entry_type="IN",
        entry_ref="secondary_arrival_in",
        from_center=from_center,
        coffee_grade=coffee_grade,
        remarks="Arrived from dispatch",
    )


def secondary_arrival_on_trash(doc, method=None):
    reverse_entries(doc.doctype, doc.name)


def secondary_processing_on_save(doc, method=None):
    center = doc.processing_center
    status = (doc.status or "").strip()
    input_form = (doc.coffee_type or "").strip()
    qty_in = flt(doc.weight_in_kg)

    if not center or status not in ("Processing", "Completed") or qty_in <= 0:
        reverse_entries(doc.doctype, doc.name)
        return

    # Consume input form
    record_transfer(
        center=center,
        status="In Processing",
        form=input_form,
        qty=qty_in,
        ref_dt=doc.doctype,
        ref_dn=doc.name,
        entry_type="OUT",
        entry_ref="secondary_proc_input",
        remarks="Secondary processing input",
    )

    output_refs = []
    if status == "Completed":
        out_center = getattr(doc, "processed_center", None) or center
        for idx, row in enumerate(doc.get("processed_output") or [], start=1):
            out_qty = flt(row.weightkg)
            entry_ref = f"secondary_proc_output_{idx}"
            if out_qty <= 0:
                reverse_entries(doc.doctype, doc.name, entry_ref=entry_ref, entry_type="IN")
                continue

            record_transfer(
                center=out_center,
                status="In Processing",
                form="Green Bean",
                qty=out_qty,
                ref_dt=doc.doctype,
                ref_dn=doc.name,
                entry_type="IN",
                entry_ref=entry_ref,
                coffee_grade=row.grade or None,
                remarks="Secondary processing output",
            )
            output_refs.append(entry_ref)

    # Drop stale output rows if any
    _cancel_missing_entries(doc.doctype, doc.name, "IN", output_refs)


def secondary_processing_on_trash(doc, method=None):
    reverse_entries(doc.doctype, doc.name)
