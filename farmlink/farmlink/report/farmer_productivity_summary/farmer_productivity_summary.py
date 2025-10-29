# Copyright (c) 2025, vulerotech and contributors

from __future__ import annotations

import frappe
from frappe.utils import add_days


def execute(filters: dict | None = None):
	filters = filters or {}

	columns = [
		{"label": "Farmer", "fieldname": "farmer_id", "fieldtype": "Link", "options": "Farmers", "width": 150},
		{"label": "Farmer Name", "fieldname": "farmer_name", "fieldtype": "Data", "width": 180},
		{"label": "Territory", "fieldname": "territory", "fieldtype": "Link", "options": "Territory", "width": 140},
		{
			"label": "Total Farmland (Ha)",
			"fieldname": "total_land",
			"fieldtype": "Float",
			"precision": 2,
			"width": 140,
		},
		{
			"label": "Coffee Fields",
			"fieldname": "coffee_fields",
			"fieldtype": "Int",
			"width": 110,
		},
		{
			"label": "Purchases (KG)",
			"fieldname": "total_weight",
			"fieldtype": "Float",
			"precision": 2,
			"width": 130,
		},
		{
			"label": "Purchases (ETB)",
			"fieldname": "total_value",
			"fieldtype": "Currency",
			"width": 140,
		},
	]

	data = get_data(filters)
	return columns, data


def get_data(filters: dict):
	conditions = []
	params: dict[str, object] = {}

	purchase_conditions = ["p.docstatus < 2"]
	if filters.get("from_date"):
		purchase_conditions.append("p.purchase_date >= %(from_date)s")
		params["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		# include the entire day for to_date by adding one day and using <
		purchase_conditions.append("p.purchase_date < %(to_date_end)s")
		params["to_date_end"] = add_days(filters["to_date"], 1)

	if filters.get("territory"):
		conditions.append("f.territory = %(territory)s")
		params["territory"] = filters["territory"]

	where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
	purchase_join = (
		"LEFT JOIN `tabPurchases` p ON p.farmer = f.name AND " + " AND ".join(purchase_conditions)
	)

	return frappe.db.sql(
		f"""
		SELECT
			f.name AS farmer_id,
			COALESCE(f.full_name, f.name) AS farmer_name,
			f.territory,
			IFNULL(f.total_farmland_ownership_in_hectares, 0) AS total_land,
			IFNULL(f.number_of_coffee_fields, 0) AS coffee_fields,
			IFNULL(SUM(p.weight_in_kg), 0) AS total_weight,
			IFNULL(SUM(p.total_price), 0) AS total_value
		FROM `tabFarmers` f
		{purchase_join}
		{where_clause}
		GROUP BY
			f.name,
			f.full_name,
			f.territory,
			f.total_farmland_ownership_in_hectares,
			f.number_of_coffee_fields
		ORDER BY
			f.territory,
			farmer_name
	""",
		params,
		as_dict=True,
	)
