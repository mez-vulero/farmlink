# Copyright (c) 2025, vulerotech and contributors

from __future__ import annotations

import frappe
from frappe.utils import add_days


def execute(filters: dict | None = None):
	filters = filters or {}

	columns = [
		{"label": "Center", "fieldname": "center", "fieldtype": "Link", "options": "Centers", "width": 150},
		{"label": "Arrivals (KG)", "fieldname": "arrival_kg", "fieldtype": "Float", "precision": 2, "width": 130},
		{"label": "Processing Input (KG)", "fieldname": "processing_input_kg", "fieldtype": "Float", "precision": 2, "width": 160},
		{"label": "Processing Output (KG)", "fieldname": "processing_output_kg", "fieldtype": "Float", "precision": 2, "width": 170},
		{"label": "Main Stock (KG)", "fieldname": "main_stock_kg", "fieldtype": "Float", "precision": 2, "width": 140},
		{"label": "Secondary Stock (KG)", "fieldname": "secondary_stock_kg", "fieldtype": "Float", "precision": 2, "width": 170},
		{"label": "In Processing (KG)", "fieldname": "in_processing_kg", "fieldtype": "Float", "precision": 2, "width": 150},
	]

	data = list(aggregate_data(filters).values())
	data.sort(key=lambda row: row["center"])
	return columns, data


def aggregate_data(filters: dict):
	results: dict[str, dict] = {}

	def ensure(center: str):
		if not center:
			return None
		return results.setdefault(
			center,
			{
				"center": center,
				"arrival_kg": 0.0,
				"processing_input_kg": 0.0,
				"processing_output_kg": 0.0,
				"main_stock_kg": 0.0,
				"secondary_stock_kg": 0.0,
				"in_processing_kg": 0.0,
			},
		)

	params: dict[str, object] = {}
	arrival_conditions = []
	processing_conditions = []
	stock_conditions = []

	if filters.get("center"):
		arrival_conditions.append("pal.center = %(center)s")
		processing_conditions.append("pp.processing_center = %(center)s")
		stock_conditions.append("csl.center = %(center)s")
		params["center"] = filters["center"]

	if filters.get("from_date"):
		arrival_conditions.append("pal.log_time >= %(from_date)s")
		processing_conditions.append("pp.logged_time >= %(from_date)s")
		stock_conditions.append("csl.posting_time >= %(from_date)s")
		params["from_date"] = filters["from_date"]

	if filters.get("to_date"):
		params["to_date_end"] = add_days(filters["to_date"], 1)
		arrival_conditions.append("pal.log_time < %(to_date_end)s")
		processing_conditions.append("pp.logged_time < %(to_date_end)s")
		stock_conditions.append("csl.posting_time < %(to_date_end)s")

	arrival_where = f"WHERE {' AND '.join(arrival_conditions)}" if arrival_conditions else ""
	processing_where = f"WHERE {' AND '.join(processing_conditions)}" if processing_conditions else ""
	stock_where = f"WHERE {' AND '.join(stock_conditions)}" if stock_conditions else ""

	for row in frappe.db.sql(
		f"""
			SELECT pal.center, SUM(pal.collected_weight) AS total_weight
			FROM `tabPrimary Arrival Log` pal
			{arrival_where}
			GROUP BY pal.center
		""",
		params,
		as_dict=True,
	):
		record = ensure(row.center)
		if record:
			record["arrival_kg"] = float(row.total_weight or 0)

	for row in frappe.db.sql(
		f"""
			SELECT
				pp.processing_center AS center,
				SUM(pp.weight_in_kg) AS input_weight,
				SUM(pp.final_output_weight_kg) AS output_weight
			FROM `tabPrimary Processing` pp
			{processing_where}
			GROUP BY pp.processing_center
		""",
		params,
		as_dict=True,
	):
		record = ensure(row.center)
		if record:
			record["processing_input_kg"] = float(row.input_weight or 0)
			record["processing_output_kg"] = float(row.output_weight or 0)

	status_map = {
		"Main Arrival": "main_stock_kg",
		"Secondary Arrival": "secondary_stock_kg",
		"In Processing": "in_processing_kg",
	}

	for row in frappe.db.sql(
		f"""
			SELECT csl.center, csl.status, SUM(csl.qty_kg) AS qty
			FROM `tabCoffee Stock Ledger` csl
			{stock_where}
			GROUP BY csl.center, csl.status
		""",
		params,
		as_dict=True,
	):
		record = ensure(row.center)
		if record:
			target = status_map.get(row.status)
			if target:
				record[target] += float(row.qty or 0)

	return results
