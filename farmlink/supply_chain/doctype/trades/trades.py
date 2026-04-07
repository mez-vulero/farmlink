import frappe
from frappe.model.document import Document
from frappe.utils import flt, cint


class Trades(Document):
    def validate(self):
        self._compute_totals()
        self._validate_status_transition()

    def _compute_totals(self):
        total_kg = 0
        total_bags = 0
        for row in self.get("table_ovaz") or []:
            row.weight_kg = flt(row.quantity) * flt(row.bag_size)
            total_kg += row.weight_kg
            total_bags += cint(row.quantity)
        self.total_quantity_kg = total_kg
        self.total_bags = total_bags
        if self.price_per_kg:
            self.total_value = flt(self.total_quantity_kg) * flt(self.price_per_kg)

    def _validate_status_transition(self):
        if self.is_new():
            return
        valid = {
            "Draft": ("Confirmed", "Cancelled"),
            "Confirmed": ("Allocated", "Cancelled"),
            "Allocated": ("Ready to Ship", "Confirmed", "Cancelled"),
            "Ready to Ship": ("Shipped", "Allocated", "Cancelled"),
            "Shipped": ("Delivered",),
            "Delivered": (),
            "Cancelled": ("Draft",),
        }
        old_status = frappe.db.get_value("Trades", self.name, "status")
        if old_status and old_status != self.status:
            allowed = valid.get(old_status, ())
            if self.status not in allowed:
                frappe.throw(f"Cannot change status from {old_status} to {self.status}")


@frappe.whitelist()
def create_cupping_order(trade_name):
    """Create a Cupping Order linked to a Trade. Returns the new Cupping Order name."""
    trade = frappe.get_doc("Trades", trade_name)

    # Get the first cert line's details for defaults
    first_row = (trade.get("table_ovaz") or [None])[0]

    cup = frappe.new_doc("Cupping Order")
    cup.trade = trade.name
    cup.export_warehouse = trade.export_warehouse
    if first_row:
        cup.coffee_grade = first_row.coffee_grade
        cup.coffee_type = first_row.coffee_type
    cup.insert()

    # Link back to the trade
    frappe.db.set_value("Trades", trade.name, "cupping_order", cup.name)

    return cup.name
