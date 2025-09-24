import frappe
from farmlink.api import _write_purchase_summary

def on_payment_change(doc, method):
    if doc.get("purchase_invoice"):
        _write_purchase_summary(doc.purchase_invoice)
