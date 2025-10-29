// Copyright (c) 2025, vulerotech and contributors
// For license information, please see license.txt

frappe.query_reports["Purchase Payment Reconciliation"] = {
	filters: [
		{
			fieldname: "collection_center",
			label: __("Collection Center"),
			fieldtype: "Link",
			options: "Centers",
		},
		{
			fieldname: "status",
			label: __("Purchase Status"),
			fieldtype: "Select",
			options: ["", "Unpaid", "Partially Paid", "Paid"].join("\n"),
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
		},
	],
};
