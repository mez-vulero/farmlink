"""
Soft-delete tombstone tracking for the mobile sync engine.

When any synced DocType is hard-deleted (on_trash hook in hooks.py), record_tombstone
inserts a Sync Tombstone row capturing {ref_doctype, ref_name, deleted_at, deleted_by,
territory, center}. The mobile app's pull endpoint queries tombstones since
last_sync_timestamp so offline clients can purge orphaned local rows.

Without tombstones, deletes are invisible to the mobile app and never propagate.
"""

import frappe
from frappe.utils import now_datetime


def record_tombstone(doc, method=None):
	territory = _resolve_territory(doc)
	center = _resolve_center(doc)

	frappe.get_doc(
		{
			"doctype": "Sync Tombstone",
			"ref_doctype": doc.doctype,
			"ref_name": doc.name,
			"deleted_at": now_datetime(),
			"deleted_by": frappe.session.user,
			"territory": territory,
			"center": center,
		}
	).insert(ignore_permissions=True)


def _resolve_territory(doc):
	for field in ("territory", "site_assigned"):
		value = getattr(doc, field, None)
		if value:
			return value

	farmer = getattr(doc, "farmer", None)
	if farmer:
		return frappe.db.get_value("Farmers", farmer, "territory")

	purchase = getattr(doc, "purchase_invoice", None)
	if purchase:
		farmer_via_purchase = frappe.db.get_value("Purchases", purchase, "farmer")
		if farmer_via_purchase:
			return frappe.db.get_value("Farmers", farmer_via_purchase, "territory")

	return None


def _resolve_center(doc):
	for field in (
		"center",
		"collection_center",
		"processing_center",
		"dispatched_from",
		"arrival_center",
		"source_center",
		"export_warehouse",
		"processed_center",
	):
		value = getattr(doc, field, None)
		if value:
			return value
	return None
