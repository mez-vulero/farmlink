"""
Sync v2 serialization helpers.

Two responsibilities:

  to_payload(doc) — convert a Frappe Document into the dict shape the mobile
    app stores in WatermelonDB. Includes child tables (one extra batched query
    per child field; the caller is responsible for *batching* across many
    parents — this helper just emits one doc).

  from_payload(data, doctype) — convert an incoming mobile payload into a dict
    safe to feed into ``frappe.get_doc({"doctype": ..., **payload})``. Strips
    fields that don't exist on the doctype meta and the mobile-only sentinels
    (custom_sync_status, frappe_id, client_id, sync_version, base_version).

sync_version_of(doc) — the integer ms-timestamp the mobile uses to detect
    conflicts. Reuses ``modified`` so we don't need a schema migration.

The legacy v1 sync_module had a 700-line ``convertFromFrappeFormat``
case-per-doctype switch on the mobile side and a parallel field-mapping table
on the backend that was never reached (FIELD_MAPPINGS was undefined). This
module replaces both with one set of generic helpers driven by Frappe meta.
The mobile app's sync engine consumes the same JSON shape regardless of
doctype; doctype-specific quirks (e.g. processing_output as a JSON string in
mobile vs. a child table on server) are handled inline here.
"""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe.utils import get_datetime


# Mobile-only fields that must never reach Frappe inserts/updates.
MOBILE_ONLY_FIELDS = frozenset(
	{
		"custom_sync_status",
		"frappe_id",
		"client_id",
		"sync_version",
		"base_version",
		"_changed",
		"_status",
	}
)

# Frappe internals we don't want to round-trip back to mobile.
SERVER_INTERNAL_FIELDS = frozenset(
	{
		"_user_tags",
		"_comments",
		"_assign",
		"_liked_by",
		"docstatus",
		"idx",
		"parent",
		"parentfield",
		"parenttype",
	}
)

# Field types we never serialize (purely cosmetic in the form layout).
COSMETIC_FIELDTYPES = frozenset(
	{
		"Section Break",
		"Column Break",
		"Tab Break",
		"HTML",
		"Heading",
		"Button",
	}
)

# Doctype-specific child-table mapping for round-tripping. Mobile stores child
# tables either as a JSON-string column (legacy) or as a list of objects (v2).
# We always emit lists; from_payload accepts either.
CHILD_TABLE_PARENTS = {
	"Primary Processing": [("processing_output", "Processed Output")],
	"Secondary Processing": [("processed_output", "Processed Output")],
	"Farmers": [
		("harvest_data", "Harvest Data"),
		("fertilizercompost_usage", "Fertilizer Usage"),
	],
	"Trades": [("table_ovaz", "Cert No Details")],
}


def sync_version_of(doc) -> int:
	modified = getattr(doc, "modified", None)
	if not modified:
		return 0
	if isinstance(modified, str):
		modified = get_datetime(modified)
	return int(modified.timestamp() * 1000)


def to_payload(doc) -> dict[str, Any]:
	"""Serialize a single Frappe doc for the mobile app."""
	meta = frappe.get_meta(doc.doctype)
	payload: dict[str, Any] = {
		"name": doc.name,
		"creation": doc.creation.isoformat() if hasattr(doc.creation, "isoformat") else doc.creation,
		"modified": doc.modified.isoformat() if hasattr(doc.modified, "isoformat") else doc.modified,
		"sync_version": sync_version_of(doc),
	}

	for field in meta.fields:
		if field.fieldtype in COSMETIC_FIELDTYPES:
			continue
		if field.fieldname in SERVER_INTERNAL_FIELDS:
			continue
		if field.fieldtype == "Table":
			payload[field.fieldname] = [
				_serialize_child(child) for child in getattr(doc, field.fieldname, []) or []
			]
		elif field.fieldtype in ("Datetime", "Date", "Time"):
			value = getattr(doc, field.fieldname, None)
			payload[field.fieldname] = value.isoformat() if hasattr(value, "isoformat") else value
		else:
			payload[field.fieldname] = getattr(doc, field.fieldname, None)
	return payload


def _serialize_child(child) -> dict[str, Any]:
	meta = frappe.get_meta(child.doctype)
	out: dict[str, Any] = {"name": child.name}
	for field in meta.fields:
		if field.fieldtype in COSMETIC_FIELDTYPES:
			continue
		if field.fieldname in SERVER_INTERNAL_FIELDS:
			continue
		out[field.fieldname] = getattr(child, field.fieldname, None)
	return out


def from_payload(data: dict, doctype: str) -> dict[str, Any]:
	"""Sanitize an incoming payload before insert/save.

	* Drops mobile-only sentinels (custom_sync_status, frappe_id, etc.)
	* Drops fields not present on the doctype meta
	* Normalizes child tables into list-of-dicts (accepts JSON-string legacy form)
	* Drops Frappe-managed timestamps (creation/modified) — server is authoritative
	"""
	if not isinstance(data, dict):
		return {}

	meta = frappe.get_meta(doctype)
	allowed_fields: dict[str, str] = {f.fieldname: f.fieldtype for f in meta.fields}
	allowed_fields["name"] = "Data"  # always allow name override

	result: dict[str, Any] = {}
	child_field_set = {fname for fname, _ in CHILD_TABLE_PARENTS.get(doctype, [])}

	for key, value in data.items():
		if key in MOBILE_ONLY_FIELDS:
			continue
		if key in ("creation", "modified", "owner", "modified_by", "docstatus", "idx"):
			# Frappe manages these; never let the mobile clobber them
			continue
		if key not in allowed_fields:
			continue

		if key in child_field_set or allowed_fields.get(key) == "Table":
			result[key] = _normalize_child_rows(value, key, doctype)
		else:
			result[key] = value

	return result


def _normalize_child_rows(value, parent_field: str, doctype: str) -> list[dict]:
	"""Accept a list, JSON-encoded string, or null and return a list of clean child dicts."""
	if not value:
		return []
	if isinstance(value, str):
		try:
			value = json.loads(value)
		except (ValueError, TypeError):
			return []
	if not isinstance(value, list):
		return []

	# Translate the mobile schema for processing_output / processed_output, which the
	# legacy mobile app sends with a 'weight' key that maps to Frappe's 'weightkg'.
	cleaned: list[dict] = []
	for row in value:
		if not isinstance(row, dict):
			continue
		row = {k: v for k, v in row.items() if k not in MOBILE_ONLY_FIELDS}
		if parent_field in ("processing_output", "processed_output") and "weight" in row and "weightkg" not in row:
			row["weightkg"] = row.pop("weight")
		# Strip Frappe internals the mobile may have echoed back
		for internal in ("name", "parent", "parentfield", "parenttype", "idx", "creation", "modified", "owner", "modified_by", "docstatus"):
			row.pop(internal, None)
		cleaned.append(row)
	return cleaned


def list_child_tables(doctype: str) -> list[tuple[str, str]]:
	"""Return [(parent_field, child_doctype), ...] for batched child fetches."""
	return list(CHILD_TABLE_PARENTS.get(doctype, []))
