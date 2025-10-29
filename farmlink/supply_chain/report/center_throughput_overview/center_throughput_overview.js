// Copyright (c) 2025, vulerotech and contributors
// For license information, please see license.txt

frappe.query_reports["Center Throughput Overview"] = {
	filters: [
		{
			fieldname: "center",
			label: __("Center"),
			fieldtype: "Link",
			options: "Centers",
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
