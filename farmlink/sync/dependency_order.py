"""
Dependency order + foreign-key map for the v2 sync engine.

The v1 module had two correctness bugs this file fixes:

  1. Several entries referenced a non-existent ``washing_stations`` table.
     The real Frappe DocType is ``Centers``; the mobile table is ``centers``.
  2. ``cupping_orders`` was processed before ``trades`` even though
     ``trades.cupping_order`` links back to it. Trades is now after
     cupping_orders, and the trade<->cupping_order back-reference is left for
     a follow-up update push (Frappe accepts null cupping_order on Trades).

PROCESSING_ORDER is the order in which push() processes each mobile table so
that parent records exist before children reference them.

LINK_FIELD_MAPPINGS maps {mobile_table: {field: target_mobile_table}} for the
fields whose values are foreign keys into another *synced* mobile table. These
get resolved through the per-push id_mappings (client_id -> Frappe name)
before insert/save. Foreign keys to non-synced doctypes (e.g. User, Bank, Customers)
are NOT listed — the mobile sends the Frappe name directly.
"""

# Mobile WatermelonDB table -> Frappe DocType name
DOCTYPE_MAPPINGS: dict[str, str] = {
	"territories": "Territory",
	"centers": "Centers",
	"suppliers": "Supplier",
	"farmers": "Farmers",
	"personnel": "Personnel",
	"farms": "Farms",
	"purchases": "Purchases",
	"payments": "Payment",
	"arrival_logs": "Primary Arrival Log",
	"primary_processing": "Primary Processing",
	"dispatches": "Primary Dispatch",
	"secondary_arrival_logs": "Secondary Arrival Log",
	"secondary_processing": "Secondary Processing",
	"export_arrival_logs": "Export Arrival Log",
	"cupping_orders": "Cupping Order",
	"trades": "Trades",
	"export_dispatches": "Export Dispatch",
}

# Reverse: Frappe DocType -> mobile table
REVERSE_DOCTYPE_MAPPINGS: dict[str, str] = {v: k for k, v in DOCTYPE_MAPPINGS.items()}

# Push order: parents before children. Personnel sits before farms because the
# mobile UI is keyed on the operating personnel; farms references farmers but
# both root from territories.
PROCESSING_ORDER: tuple[str, ...] = (
	"territories",
	"centers",
	"suppliers",
	"farmers",
	"personnel",
	"farms",
	"purchases",
	"payments",
	"arrival_logs",
	"primary_processing",
	"dispatches",
	"secondary_arrival_logs",
	"secondary_processing",
	"export_arrival_logs",
	"cupping_orders",
	"trades",
	"export_dispatches",
)

# Cross-table foreign keys among synced tables only.
LINK_FIELD_MAPPINGS: dict[str, dict[str, str]] = {
	"territories": {
		"parent_territory": "territories",
	},
	"centers": {
		"territory": "territories",
	},
	"suppliers": {
		"territory": "territories",
	},
	"farmers": {
		"territory": "territories",
		"site_name": "centers",
	},
	"personnel": {
		"site_assigned": "territories",
		"collection_center": "centers",
	},
	"farms": {
		"territory": "territories",
		"farmer": "farmers",
	},
	"purchases": {
		"farmer": "farmers",
		"collection_center": "centers",
		"supplier": "suppliers",
	},
	"payments": {
		"purchase_invoice": "purchases",
		"farmer": "farmers",
	},
	"arrival_logs": {
		"center": "centers",
	},
	"primary_processing": {
		"processing_center": "centers",
		"temporary_warehouse": "centers",
	},
	"dispatches": {
		"dispatched_from": "centers",
		"destination": "centers",
		"destination_territory": "territories",
	},
	"secondary_arrival_logs": {
		"arrival_center": "centers",
		"dispatch_log": "dispatches",
	},
	"secondary_processing": {
		"processing_center": "centers",
		"processed_center": "centers",
	},
	"export_arrival_logs": {
		"secondary_processing_ref": "secondary_processing",
		"source_center": "centers",
		"arrival_center": "centers",
	},
	"cupping_orders": {
		"export_warehouse": "centers",
		"secondary_processing_ref": "secondary_processing",
		"trade": "trades",
	},
	"trades": {
		"export_warehouse": "centers",
		"cupping_order": "cupping_orders",
	},
	"export_dispatches": {
		"trade": "trades",
		"export_warehouse": "centers",
	},
}
