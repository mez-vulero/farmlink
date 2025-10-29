# Copyright (c) 2025, vulerotech and contributors

from __future__ import annotations

import frappe
from frappe.utils import add_days


def execute(filters: dict | None = None):
	filters = filters or {}

	columns = [
		{"label": "Purchase", "fieldname": "purchase", "fieldtype": "Link", "options": "Purchases", "width": 140},
		{"label": "Date", "fieldname": "purchase_date", "fieldtype": "Date", "width": 110},
		{
			"label": "Collection Center",
			"fieldname": "collection_center",
			"fieldtype": "Link",
			"options": "Centers",
			"width": 150,
		},
		{"label": "Farmer", "fieldname": "farmer", "fieldtype": "Link", "options": "Farmers", "width": 140},
		{"label": "Purchase Value (ETB)", "fieldname": "total_price", "fieldtype": "Currency", "width": 160},
		{"label": "Recorded Paid (ETB)", "fieldname": "recorded_paid", "fieldtype": "Currency", "width": 160},
		{"label": "Outstanding (ETB)", "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 150},
		{"label": "Paid via Payments (ETB)", "fieldname": "paid_amount", "fieldtype": "Currency", "width": 190},
		{
			"label": "Variance (ETB)",
			"fieldname": "variance",
			"fieldtype": "Currency",
			"width": 150,
		},
	]

	data = get_data(filters)
	return columns, data


def get_data(filters: dict):
	conditions = ["p.docstatus < 2"]
	params: dict[str, object] = {}

	if filters.get("collection_center"):
		conditions.append("p.collection_center = %(collection_center)s")
		params["collection_center"] = filters["collection_center"]

	if filters.get("status"):
		conditions.append("p.status = %(status)s")
		params["status"] = filters["status"]

	if filters.get("from_date"):
		conditions.append("p.purchase_date >= %(from_date)s")
		params["from_date"] = filters["from_date"]

	if filters.get("to_date"):
		conditions.append("p.purchase_date < %(to_date_end)s")
		params["to_date_end"] = add_days(filters["to_date"], 1)

	where_clause = " AND ".join(conditions)

	return frappe.db.sql(
		f"""
		SELECT
			p.name AS purchase,
			p.purchase_date,
			p.collection_center,
			p.farmer,
			IFNULL(p.total_price, 0) AS total_price,
			IFNULL(p.total_price, 0) - IFNULL(p.outstanding_amount, 0) AS recorded_paid,
			IFNULL(p.outstanding_amount, 0) AS outstanding_amount,
			IFNULL(SUM(pay.payment_amount), 0) AS paid_amount,
			IFNULL(SUM(pay.payment_amount), 0)
				- (IFNULL(p.total_price, 0) - IFNULL(p.outstanding_amount, 0)) AS variance
		FROM `tabPurchases` p
		LEFT JOIN `tabPayment` pay
			ON pay.purchase_invoice = p.name AND pay.docstatus = 1
		WHERE {where_clause}
		GROUP BY
			p.name,
			p.purchase_date,
			p.collection_center,
			p.farmer,
			p.total_price,
			p.outstanding_amount
		ORDER BY p.purchase_date DESC, p.name DESC
	""",
		params,
		as_dict=True,
	)
