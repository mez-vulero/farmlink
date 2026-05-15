# Copyright (c) 2025, vulerotech and contributors
# For license information, please see license.txt
"""
Doctype metadata endpoints for the mobile app.

The mobile app needs a few Select-field option lists (e.g. Farmer naming
series) that admins maintain on the doctype in the Frappe Desk. Hardcoding
them in the mobile bundle means every option change requires a new release;
exposing them as a small read-only endpoint lets admins edit the doctype and
have the change reach phones on the next refresh.

This module deliberately exposes one narrow endpoint per use-case rather than
a generic "give me any field's options" RPC, so the surface area stays
auditable. Add more endpoints here as new mobile pickers need them.
"""

from __future__ import annotations

import frappe


@frappe.whitelist()
def farmer_naming_series() -> dict[str, list[str]]:
	"""Return the live `options` list for the Farmers doctype's `naming_series` field.

	Admins maintain these in the Farmers doctype's Series field (newline-
	separated). The mobile NamingSeriesSelector caches the result in
	AsyncStorage and refreshes on every render of the Add Farmer screen, so a
	doctype edit propagates without requiring a mobile release.

	Returns ``{"options": [...]}`` — list of non-empty trimmed strings, in
	doctype order. Empty list if the field has no options (which would be a
	configuration bug, but we don't throw — the mobile falls back to its
	hardcoded list).
	"""
	field = frappe.get_meta("Farmers").get_field("naming_series")
	raw = (field.options or "") if field else ""
	options = [line.strip() for line in raw.split("\n") if line.strip()]
	return {"options": options}
