# Copyright (c) 2025, vulerotech and contributors

from __future__ import annotations

import json

import frappe


SUPPLY_CHAIN_NUMBER_CARDS = [
    {
        "name": "Average Price Rate (7 Days)",
        "label": "Average Price Rate (7 Days)",
        "document_type": "Purchases",
        "function": "Average",
        "aggregate_function_based_on": "price_rate_of_the_day",
        "dynamic_filters_json": json.dumps(
            [
                [
                    "Purchases",
                    "purchase_date",
                    "between",
                    "[frappe.datetime.add_days(frappe.datetime.nowdate(), -6), frappe.datetime.nowdate()]",
                ]
            ]
        ),
        "filters_json": "[]",
        "currency": "ETB",
    },
    {
        "name": "Purchases (ETB)",
        "label": "Purchases (ETB)",
        "document_type": "Purchases",
        "function": "Sum",
        "aggregate_function_based_on": "total_price",
        "filters_json": "[]",
        "currency": "ETB",
    },
    {
        "name": "Total Payments Made",
        "label": "Total Payments Made",
        "document_type": "Payment",
        "function": "Sum",
        "aggregate_function_based_on": "payment_amount",
        "filters_json": json.dumps([["Payment", "docstatus", "=", 1]]),
        "currency": "ETB",
    },
    {
        "name": "Purchases Made(KG)",
        "label": "Purchases Made(KG)",
        "document_type": "Purchases",
        "function": "Sum",
        "aggregate_function_based_on": "weight_in_kg",
        "filters_json": "[]",
        "currency": "",
    },
    {
        "name": "Outstanding Purchases",
        "label": "Outstanding Purchases",
        "document_type": "Purchases",
        "function": "Sum",
        "aggregate_function_based_on": "outstanding_amount",
        "filters_json": "[]",
        "currency": "ETB",
    },
    {
        "name": "Purchases Today (KG)",
        "label": "Purchases Today (KG)",
        "document_type": "Purchases",
        "function": "Sum",
        "aggregate_function_based_on": "weight_in_kg",
        "dynamic_filters_json": json.dumps(
            [
                [
                    "Purchases",
                    "purchase_date",
                    "between",
                    "[frappe.datetime.get_today(), frappe.datetime.add_days(frappe.datetime.get_today(), 1)]",
                ]
            ]
        ),
        "currency": "",
    },
    {
        "name": "Payments Today",
        "label": "Payments Today",
        "document_type": "Payment",
        "function": "Sum",
        "aggregate_function_based_on": "payment_amount",
        "dynamic_filters_json": json.dumps(
            [
                [
                    "Payment",
                    "payment_date",
                    "between",
                    "[frappe.datetime.get_today(), frappe.datetime.add_days(frappe.datetime.get_today(), 1)]",
                ]
            ]
        ),
        "currency": "ETB",
    },
]

SUPPLY_CHAIN_CHARTS = [
    {
        "name": "Purchase Volume by Cherry Grade",
        "chart_name": "Purchase Volume by Cherry Grade",
        "chart_type": "Group By",
        "document_type": "Purchases",
        "group_by_type": "Sum",
        "group_by_based_on": "collection_center",
        "aggregate_function_based_on": "weight_in_kg",
        "filters_json": "[]",
        "dynamic_filters_json": json.dumps(
            [
                [
                    "Purchases",
                    "purchase_date",
                    "between",
                    "[frappe.datetime.add_days(frappe.datetime.nowdate(), -29), frappe.datetime.nowdate()]",
                ]
            ]
        ),
        "type": "Bar",
    },
    {
        "name": "Primary Arrival Maturity Mix",
        "chart_name": "Primary Arrival Maturity Mix",
        "chart_type": "Group By",
        "document_type": "Primary Arrival Log",
        "group_by_type": "Sum",
        "group_by_based_on": "maturity",
        "aggregate_function_based_on": "collected_weight",
        "filters_json": "[]",
        "type": "Pie",
    },
    {
        "name": "Coffee Stock Status",
        "chart_name": "Coffee Stock Status",
        "chart_type": "Group By",
        "document_type": "Coffee Stock Ledger",
        "group_by_type": "Sum",
        "group_by_based_on": "status",
        "aggregate_function_based_on": "qty_kg",
        "filters_json": "[]",
        "type": "Bar",
    },
    {
        "name": "Export Grade Allocation",
        "chart_name": "Export Grade Allocation",
        "chart_type": "Group By",
        "document_type": "Cert No Details",
        "parent_document_type": "Trades",
        "group_by_type": "Sum",
        "group_by_based_on": "coffee_grade",
        "aggregate_function_based_on": "quantity",
        "filters_json": "[]",
        "type": "Donut",
    },
]

FARMLINK_NUMBER_CARDS = [
    {
        "name": "Total Farmers",
        "label": "Total Farmers",
        "document_type": "Farmers",
        "function": "Count",
        "filters_json": "[]",
        "show_percentage_stats": 0,
    },
    {
        "name": "Total Farms",
        "label": "Total Farms",
        "document_type": "Farms",
        "function": "Count",
        "filters_json": "[]",
        "show_percentage_stats": 0,
    },
    {
        "name": "Total Farm Area in Ha",
        "label": "Total Farm Area in Ha",
        "document_type": "Farmers",
        "function": "Sum",
        "aggregate_function_based_on": "total_farmland_ownership_in_hectares",
        "filters_json": "[]",
        "show_percentage_stats": 0,
        "show_full_number": 1,
    },
    {
        "name": "Active Collection Centers",
        "label": "Active Collection Centers",
        "document_type": "Centers",
        "function": "Count",
        "filters_json": json.dumps([["Centers", "status", "=", "Active"]]),
        "show_percentage_stats": 0,
    },
    {
        "name": "Purchases (KG)",
        "label": "Purchases (KG)",
        "document_type": "Purchases",
        "function": "Sum",
        "aggregate_function_based_on": "weight_in_kg",
        "filters_json": "[]",
    },
    {
        "name": "Female Farmers",
        "label": "Female Farmers",
        "document_type": "Farmers",
        "function": "Count",
        "filters_json": json.dumps([["Farmers", "gender", "=", "Female"]]),
        "show_percentage_stats": 0,
    },
    {
        "name": "Bank Preferred Farmers",
        "label": "Bank Preferred Farmers",
        "document_type": "Farmers",
        "function": "Count",
        "filters_json": json.dumps([["Farmers", "preferred_payment_method", "=", "Bank"]]),
        "show_percentage_stats": 0,
    },
    {
        "name": "Active Washing Stations",
        "label": "Active Washing Stations",
        "document_type": "Centers",
        "function": "Count",
        "filters_json": json.dumps(
            [
                ["Centers", "status", "=", "Active"],
                ["Centers", "type", "=", "Washing Station"],
            ]
        ),
        "show_percentage_stats": 0,
    },
]

FARMLINK_CHARTS = [
    {
        "name": "Daily Purchase in Volume",
        "chart_name": "Daily Purchase in Volume",
        "chart_type": "Sum",
        "document_type": "Purchases",
        "based_on": "purchase_date",
        "value_based_on": "weight_in_kg",
        "timeseries": 1,
        "time_interval": "Daily",
        "timespan": "Last Week",
        "type": "Line",
    },
    {
        "name": "Farmer by Territory",
        "chart_name": "Farmer by Territory",
        "chart_type": "Group By",
        "document_type": "Farmers",
        "group_by_type": "Count",
        "group_by_based_on": "territory",
        "type": "Donut",
    },
    {
        "name": "Farmers by Gender",
        "chart_name": "Farmers by Gender",
        "chart_type": "Group By",
        "document_type": "Farmers",
        "group_by_type": "Count",
        "group_by_based_on": "gender",
        "type": "Donut",
    },
    {
        "name": "Purchase Price Trend",
        "chart_name": "Purchase Price Trend",
        "chart_type": "Average",
        "document_type": "Purchases",
        "timeseries": 1,
        "based_on": "purchase_date",
        "value_based_on": "price_rate_of_the_day",
        "time_interval": "Daily",
        "timespan": "Last Month",
        "type": "Line",
    },
    {
        "name": "Payment Method Mix",
        "chart_name": "Payment Method Mix",
        "chart_type": "Group By",
        "document_type": "Payment",
        "group_by_type": "Sum",
        "group_by_based_on": "mode_of_payment",
        "aggregate_function_based_on": "payment_amount",
        "filters_json": json.dumps([["Payment", "docstatus", "=", 1]]),
        "type": "Donut",
    },
    {
        "name": "Supplier Contribution by Volume",
        "chart_name": "Supplier Contribution by Volume",
        "chart_type": "Group By",
        "document_type": "Purchases",
        "group_by_type": "Sum",
        "group_by_based_on": "supplier",
        "aggregate_function_based_on": "weight_in_kg",
        "filters_json": json.dumps([["Purchases", "docstatus", "=", 1]]),
        "type": "Bar",
        "number_of_groups": 10,
    },
    {
        "name": "Farmland by Territory",
        "chart_name": "Farmland by Territory",
        "chart_type": "Group By",
        "document_type": "Farmers",
        "group_by_type": "Sum",
        "group_by_based_on": "territory",
        "aggregate_function_based_on": "total_farmland_ownership_in_hectares",
        "filters_json": "[]",
        "type": "Bar",
        "number_of_groups": 10,
    },
]

REPORT_DEFINITIONS = [
    {
        "name": "Farmer Productivity Summary",
        "module": "FarmLink",
        "ref_doctype": "Farmers",
        "report_type": "Script Report",
        "json": json.dumps(
            {
                "filters": [
                    {"fieldname": "territory", "fieldtype": "Link", "label": "Territory", "options": "Territory"},
                    {"fieldname": "from_date", "fieldtype": "Date", "label": "From Date"},
                    {"fieldname": "to_date", "fieldtype": "Date", "label": "To Date"},
                ]
            }
        ),
        "roles": ["System Manager", "Farmlink Manager"],
    },
    {
        "name": "Purchase Payment Reconciliation",
        "module": "Supply Chain",
        "ref_doctype": "Purchases",
        "report_type": "Script Report",
        "json": json.dumps(
            {
                "filters": [
                    {"fieldname": "collection_center", "fieldtype": "Link", "label": "Collection Center", "options": "Centers"},
                    {"fieldname": "status", "fieldtype": "Select", "label": "Purchase Status", "options": "\nUnpaid\nPartially Paid\nPaid"},
                    {"fieldname": "from_date", "fieldtype": "Date", "label": "From Date"},
                    {"fieldname": "to_date", "fieldtype": "Date", "label": "To Date"},
                ]
            }
        ),
        "roles": ["System Manager", "Farmlink Manager", "Finance Officer"],
    },
    {
        "name": "Center Throughput Overview",
        "module": "Supply Chain",
        "ref_doctype": "Centers",
        "report_type": "Script Report",
        "json": json.dumps(
            {
                "filters": [
                    {"fieldname": "center", "fieldtype": "Link", "label": "Center", "options": "Centers"},
                    {"fieldname": "from_date", "fieldtype": "Date", "label": "From Date"},
                    {"fieldname": "to_date", "fieldtype": "Date", "label": "To Date"},
                ]
            }
        ),
        "roles": ["System Manager", "Farmlink Manager"],
    },
]


def execute():
    """Ensure workspace dependencies (number cards and charts) exist."""
    create_number_cards(SUPPLY_CHAIN_NUMBER_CARDS, module="Supply Chain")
    create_dashboard_charts(SUPPLY_CHAIN_CHARTS, module="Supply Chain")

    create_number_cards(FARMLINK_NUMBER_CARDS, module="FarmLink")
    create_dashboard_charts(FARMLINK_CHARTS, module="FarmLink")
    create_reports()


def create_number_cards(definitions: list[dict], module: str) -> None:
    base_defaults = {
        "doctype": "Number Card",
        "type": "Document Type",
        "module": module,
        "is_standard": 1,
        "is_public": 1,
        "show_percentage_stats": 1,
        "stats_time_interval": "Daily",
        "show_full_number": 0,
        "color": None,
        "background_color": None,
        "filters_json": "[]",
        "currency": "",
    }

    for card in definitions:
        values = base_defaults.copy()
        values.update(card)
        upsert_doc("Number Card", values["name"], values)


def create_dashboard_charts(definitions: list[dict], module: str) -> None:
    base_defaults = {
        "doctype": "Dashboard Chart",
        "is_public": 1,
        "is_standard": 1,
        "module": module,
        "filters_json": "[]",
        "dynamic_filters_json": None,
        "number_of_groups": 0,
        "timeseries": 0,
        "timespan": "",
        "time_interval": "",
        "use_report_chart": 0,
        "type": "Bar",
        "color": None,
        "custom_options": None,
    }

    for chart in definitions:
        values = base_defaults.copy()
        # ensure each chart gets its own list
        values["y_axis"] = []
        values.update(chart)
        values.setdefault("y_axis", [])
        upsert_doc("Dashboard Chart", values["name"], values)


def create_reports():
    for report in REPORT_DEFINITIONS:
        values = {
            "doctype": "Report",
            "is_standard": "Yes",
            "prepared_report": 0,
            "disabled": 0,
            "include_prepared_report": 0,
            "columns": [],
            "roles": [{"role": role} for role in report.get("roles", [])],
        }
        values.update({k: v for k, v in report.items() if k not in {"roles"}})
        values.setdefault("report_name", values["name"])
        upsert_doc("Report", values["name"], values)


def upsert_doc(doctype: str, name: str, values: dict) -> None:
    """Create or update a document with the provided values."""
    if frappe.db.exists(doctype, name):
        doc = frappe.get_doc(doctype, name)
        has_changes = False

        for field, value in values.items():
            if doc.get(field) != value:
                doc.set(field, value)
                has_changes = True

        if has_changes:
            doc.flags.ignore_mandatory = True
            doc.save(ignore_permissions=True)
    else:
        doc = frappe.new_doc(doctype)
        doc.flags.ignore_mandatory = True
        doc.update(values)
        doc.insert(ignore_permissions=True)
