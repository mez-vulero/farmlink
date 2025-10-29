// Copyright (c) 2025, vulerotech and contributors
// For license information, please see license.txt

frappe.query_reports["Farmer Productivity Summary"] = {
	filters: [
		{
			fieldname: "territory",
			label: __("Territory"),
			fieldtype: "Link",
			options: "Territory",
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
