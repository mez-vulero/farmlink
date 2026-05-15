"""
Server-side permission_query_conditions for FarmLink synced DocTypes.

Each filterable DocType has a wrapper function (referenced from hooks.py) that
returns a SQL fragment Frappe injects into list/report queries to enforce
row-level filtering by Personnel.site_assigned (Territory) and
Personnel.collection_center.

Bypasses (return empty string = no filter):
  - System Manager
  - Farmlink Manager  (legacy admin role; preserves existing Desk behaviour)

Deny (return "1=0" = no rows):
  - User has no Personnel record AND none of the bypass roles above

Area Manager designation gets the full territory subtree (descendants of their
site_assigned). Other designations are scoped tightly to their assigned center
or, where no center field exists, their assigned territory.
"""

import frappe
from frappe.utils.nestedset import get_descendants_of


BYPASS_ROLES = ("System Manager", "Farmlink Manager")


def _has_bypass_role(user: str) -> bool:
	roles = set(frappe.get_roles(user))
	return any(role in roles for role in BYPASS_ROLES)


def _get_personnel(user: str):
	return frappe.db.get_value(
		"Personnel",
		{"user_id": user},
		["name", "site_assigned", "collection_center", "designation"],
		as_dict=True,
	)


def _territory_subtree_clause(table: str, field: str, root_territory: str) -> str:
	descendants = get_descendants_of("Territory", root_territory) or []
	territories = [root_territory, *descendants]
	placeholders = ", ".join(frappe.db.escape(t) for t in territories)
	return f"`{table}`.`{field}` IN ({placeholders})"


def _build_filter(
	user: str,
	table: str,
	territory_field: str | None = None,
	center_field: str | None = None,
) -> str:
	if not user or user == "Guest":
		return "1=0"

	if _has_bypass_role(user):
		return ""

	personnel = _get_personnel(user)
	if not personnel:
		return "1=0"

	is_area_manager = (personnel.designation or "").strip() == "Area Manager"
	clauses: list[str] = []

	if center_field and personnel.collection_center:
		clauses.append(
			f"`{table}`.`{center_field}` = {frappe.db.escape(personnel.collection_center)}"
		)
	elif territory_field and personnel.site_assigned:
		if is_area_manager:
			clauses.append(
				_territory_subtree_clause(table, territory_field, personnel.site_assigned)
			)
		else:
			clauses.append(
				f"`{table}`.`{territory_field}` = {frappe.db.escape(personnel.site_assigned)}"
			)

	if not clauses:
		return "1=0"

	return " AND ".join(clauses)


# ---------- Per-doctype wrappers (referenced from hooks.py) ----------

def get_for_farmers(user):
	return _build_filter(user, "tabFarmers", territory_field="territory")


def get_for_farms(user):
	return _build_filter(user, "tabFarms", territory_field="territory")


def get_for_purchases(user):
	return _build_filter(user, "tabPurchases", center_field="collection_center")


def get_for_payment(user):
	if not user or user == "Guest":
		return "1=0"
	if _has_bypass_role(user):
		return ""
	personnel = _get_personnel(user)
	if not personnel or not personnel.collection_center:
		return "1=0"
	return (
		"`tabPayment`.`purchase_invoice` IN ("
		"SELECT `name` FROM `tabPurchases` WHERE `collection_center` = "
		f"{frappe.db.escape(personnel.collection_center)})"
	)


def get_for_primary_arrival_log(user):
	return _build_filter(user, "tabPrimary Arrival Log", center_field="center")


def get_for_primary_dispatch(user):
	return _build_filter(
		user,
		"tabPrimary Dispatch",
		center_field="dispatched_from",
		territory_field="territory",
	)


def get_for_primary_processing(user):
	return _build_filter(
		user, "tabPrimary Processing", center_field="processing_center"
	)


def get_for_secondary_processing(user):
	return _build_filter(
		user, "tabSecondary Processing", center_field="processing_center"
	)


def get_for_secondary_arrival_log(user):
	return _build_filter(
		user, "tabSecondary Arrival Log", center_field="arrival_center"
	)


def get_for_export_arrival_log(user):
	return _build_filter(
		user, "tabExport Arrival Log", center_field="arrival_center"
	)


def get_for_cupping_order(user):
	return _build_filter(user, "tabCupping Order", center_field="export_warehouse")


def get_for_trades(user):
	return _build_filter(user, "tabTrades", center_field="export_warehouse")


def get_for_export_dispatch(user):
	return _build_filter(
		user, "tabExport Dispatch", center_field="export_warehouse"
	)


def get_for_centers(user):
	return _build_filter(user, "tabCenters", territory_field="territory")


def get_for_territory(user):
	if not user or user == "Guest":
		return "1=0"
	if _has_bypass_role(user):
		return ""
	personnel = _get_personnel(user)
	if not personnel or not personnel.site_assigned:
		return "1=0"
	if (personnel.designation or "").strip() == "Area Manager":
		return _territory_subtree_clause("tabTerritory", "name", personnel.site_assigned)
	return f"`tabTerritory`.`name` = {frappe.db.escape(personnel.site_assigned)}"


def get_for_supplier(user):
	return _build_filter(user, "tabSupplier", territory_field="territory")


def get_for_personnel(user):
	if not user or user == "Guest":
		return "1=0"
	if _has_bypass_role(user):
		return ""
	return f"`tabPersonnel`.`user_id` = {frappe.db.escape(user)}"


def get_for_receipt_string(user):
	"""Global config — every signed-in user with read permission sees every row.

	Receipt strings are not territory- or center-scoped: a label printed in
	one center's purchase receipt should be the same one printed in another's.
	Guests are still denied; the standard role check on the DocType decides
	who can read.
	"""
	if not user or user == "Guest":
		return "1=0"
	return ""
