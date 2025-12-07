# utils/csl.py
import frappe
from frappe import _
from frappe.utils import now_datetime, flt

CSL = "Coffee Stock Ledger"


def _net_sum_query(filters: dict, include_status=False) -> float:
    clauses = ["is_cancelled=0"]
    params = []

    def add(k, field):
        if filters.get(k) is None:
            return
        clauses.append(f"{field}=%s")
        params.append(filters[k])

    add("center", "center")
    if include_status:
        add("status", "status")
    add("coffee_form", "coffee_form")
    add("batch_ref", "batch_ref")
    add("coffee_grade", "coffee_grade")
    add("reference_doctype", "reference_doctype")
    add("reference_name", "reference_name")

    where = " AND ".join(clauses)
    rows = frappe.db.sql(
        f"""
        SELECT COALESCE(
            SUM(
                CASE WHEN entry_type='IN' THEN qty_kg ELSE -qty_kg END
            ),0)
        FROM `tab{CSL}`
        WHERE {where}
    """,
        params,
    )
    return flt(rows[0][0] if rows else 0)


@frappe.whitelist()
def center_balance(*, center, form, batch_ref=None, coffee_grade=None, status=None):
    """Net balance (IN-OUT) for a center and form, optionally narrowed."""
    return _net_sum_query(
        {
            "center": center,
            "coffee_form": form,
            "batch_ref": batch_ref,
            "coffee_grade": coffee_grade,
            "status": status,
        },
        include_status=bool(status),
    )


@frappe.whitelist()
def sum_csl_qty(
    *, center, status, form, batch_ref=None, ref_dt=None, ref_dn=None, coffee_grade=None
):
    """Backward-compatible net qty for a specific status bucket."""
    return _net_sum_query(
        {
            "center": center,
            "status": status,
            "coffee_form": form,
            "batch_ref": batch_ref,
            "reference_doctype": ref_dt,
            "reference_name": ref_dn,
            "coffee_grade": coffee_grade,
        },
        include_status=True,
    )


def _validate_out_qty(center, form, qty, batch_ref=None, coffee_grade=None):
    available = center_balance(
        center=center, form=form, batch_ref=batch_ref, coffee_grade=coffee_grade
    )
    if qty > available:
        frappe.throw(
            _("Not enough stock at {0} for {1}. Available: {2}, requested: {3}").format(
                center, form, available, qty
            )
        )


@frappe.whitelist()
def record_transfer(
    *,
    center,
    status,
    form,
    qty,
    ref_dt,
    ref_dn,
    entry_type,
    entry_ref=None,
    from_center=None,
    to_center=None,
    batch_ref=None,
    coffee_grade=None,
    remarks="",
):
    """
    Create or update a CSL row for a specific doc + entry_ref.
    - entry_type: IN | OUT
    - entry_ref: caller-provided id to make the posting idempotent per doc
    """
    entry_type = (entry_type or "").upper()
    if entry_type not in ("IN", "OUT"):
        frappe.throw(_("Entry Type must be IN or OUT"))

    qty = flt(qty)
    entry_ref = entry_ref or ""

    if qty <= 0:
        # nothing to post; cancel any existing rows for this ref
        reverse_entries(ref_dt, ref_dn, entry_ref=entry_ref, entry_type=entry_type)
        return None

    if entry_type == "OUT":
        _validate_out_qty(center=center, form=form, qty=qty, batch_ref=batch_ref, coffee_grade=coffee_grade)

    filters = {
        "reference_doctype": ref_dt,
        "reference_name": ref_dn,
        "entry_type": entry_type,
        "entry_ref": entry_ref,
        "is_cancelled": 0,
    }

    payload = {
        "posting_time": now_datetime(),
        "center": center,
        "from_center": from_center,
        "to_center": to_center,
        "status": status,
        "coffee_form": form,
        "coffee_grade": coffee_grade,
        "qty_kg": qty,
        "reference_doctype": ref_dt,
        "reference_name": ref_dn,
        "remarks": remarks,
        "is_cancelled": 0,
        "batch_ref": batch_ref,
        "entry_ref": entry_ref,
        "entry_type": entry_type,
    }

    existing = frappe.db.get_value(CSL, filters, "name")
    if existing:
        frappe.db.set_value(CSL, existing, payload)
        return existing

    doc = frappe.get_doc({"doctype": CSL, **payload})
    doc.insert(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def reverse_entries(ref_dt, ref_dn, entry_ref=None, entry_type=None):
    """Mark CSL rows for a document as cancelled (optionally narrowed)."""
    filters = {
        "reference_doctype": ref_dt,
        "reference_name": ref_dn,
        "is_cancelled": 0,
    }
    if entry_ref is not None:
        filters["entry_ref"] = entry_ref
    if entry_type:
        filters["entry_type"] = entry_type.upper()

    names = frappe.get_all(CSL, filters=filters, pluck="name")
    for name in names:
        frappe.db.set_value(CSL, name, "is_cancelled", 1)
    return names


# Backwards compatibility wrapper
@frappe.whitelist()
def post_csl(*, center, status, form, qty, ref_dt, ref_dn, batch_ref=None, remarks="", cancelled=0):
    entry_type = "OUT" if cancelled else "IN"
    return record_transfer(
        center=center,
        status=status,
        form=form,
        qty=qty,
        ref_dt=ref_dt,
        ref_dn=ref_dn,
        entry_type=entry_type,
        entry_ref="legacy_post_csl",
        batch_ref=batch_ref,
        remarks=remarks,
    )


@frappe.whitelist()
def get_center_type(center_name: str) -> str:
    return frappe.db.get_value("Centers", center_name, "type") or ""
