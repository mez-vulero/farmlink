import frappe


def execute():
	"""Ensure Farmers -> Payment link uses the actual field name."""
	frappe.reload_doc("farmlink", "doctype", "farmers")

	link_name = frappe.db.exists(
		"DocType Link",
		{
			"parent": "Farmers",
			"parentfield": "links",
			"link_doctype": "Payment",
		},
	)

	if not link_name:
		return

	if frappe.db.get_value("DocType Link", link_name, "link_fieldname") == "farmer":
		return

	frappe.db.set_value("DocType Link", link_name, "link_fieldname", "farmer")
