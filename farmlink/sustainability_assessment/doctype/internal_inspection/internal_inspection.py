# Copyright (c) 2025, vulerotech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


ANSWER_OPTIONS = ["Yes", "No", "Partially Applicable", "Not Applicable"]

class InternalInspection(Document):
    def validate(self):
        # Generate on first save, and regenerate if template changed on a draft
        if self.checklist_template:
            if self.is_new():
                if not self.items:
                    generate_items_from_template(self)
            else:
                # template changed? rebuild items
                try:
                    prev = self.get_db_value("checklist_template")
                except Exception:
                    prev = None
                if prev != self.checklist_template:
                    self.items = []
                    generate_items_from_template(self)

@frappe.whitelist()
def regenerate_items(inspection_name: str, force=False):
    doc = frappe.get_doc("Internal Inspection", inspection_name)
    if doc.docstatus != 0:
        frappe.throw("You can only regenerate items while the document is in Draft.")
    if doc.items and not force:
        frappe.throw("Items already exist. Pass force=1 to replace them.")
    doc.items = []
    generate_items_from_template(doc)
    doc.save(ignore_permissions=True)
    return {"ok": True, "items": len(doc.items)}

def generate_items_from_template(inspection_doc: "InternalInspection"):
    if not inspection_doc.checklist_template:
        return
    tmpl = frappe.get_doc("Checklist Template", inspection_doc.checklist_template)

    # optional: copy these for filtering (add these fields to Internal Inspection if you want)
#    if hasattr(inspection_doc, "scheme_version"):
#        inspection_doc.scheme_version = tmpl.scheme_version
#    if hasattr(inspection_doc, "checklist_type"):
#        inspection_doc.checklist_type = tmpl.checklist_type

    rows = frappe.get_all(
        "Checklist Template Item",
        filters={"parent": tmpl.name, "parenttype": "Checklist Template", "parentfield": "items"},
        fields=[
            "name","section","subsection","requirement_code","requirement_text","guidance",
            "item_kind","severity","evidence_mode","idx"
        ],
        order_by="idx asc"
    )

    for r in rows:
        inspection_doc.append("items", {
            "checklist_template_item": r["name"],
            "section": r["section"],
            "subsection": r["subsection"],
            "requirement_code": r["requirement_code"],
            "requirement_text": r["requirement_text"],
            "guidance": r["guidance"],
            "item_kind": r["item_kind"],
            "severity": r["severity"],
            "evidence_mode": r["evidence_mode"],
            "answer": "",           # force user to choose
            "comment": "",
            "evidence": None        # single Attach
        })
