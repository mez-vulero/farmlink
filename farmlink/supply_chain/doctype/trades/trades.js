frappe.ui.form.on("Trades", {
	refresh(frm) {
		// Filter export_warehouse to Export Warehouse / Main Warehouse centers
		frm.set_query("export_warehouse", function () {
			return {
				filters: { type: ["in", ["Export Warehouse", "Main Warehouse"]] },
			};
		});

		// Show green bean balance when warehouse is selected
		if (frm.doc.export_warehouse) {
			frappe.call({
				method: "farmlink.utils.csl.center_balance",
				args: { center: frm.doc.export_warehouse, form: "Green Bean" },
				callback: function (r) {
					if (r.message !== undefined) {
						frm.dashboard.add_indicator(
							__("Green Bean Available: {0} kg", [flt(r.message).toFixed(2)]),
							r.message > 0 ? "green" : "orange"
						);
					}
				},
			});
		}

		// "Create Cupping Order" button — only on saved, non-cancelled trades
		if (!frm.is_new() && frm.doc.status !== "Cancelled") {
			frm.add_custom_button(__("Create Cupping Order"), function () {
				frappe.call({
					method: "farmlink.supply_chain.doctype.trades.trades.create_cupping_order",
					args: { trade_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Creating Cupping Order..."),
					callback: function (r) {
						if (r.message) {
							frappe.set_route("Form", "Cupping Order", r.message);
						}
					},
				});
			}, __("Actions"));
		}

		// Show linked cupping orders
		if (frm.doc.cupping_order) {
			frm.dashboard.add_indicator(
				__("Cupping Order: {0}", [frm.doc.cupping_order]),
				"blue"
			);
		}
	},

	price_per_kg(frm) {
		_compute_total(frm);
	},
});

frappe.ui.form.on("Cert No Details", {
	quantity(frm, cdt, cdn) {
		_compute_row_weight(frm, cdt, cdn);
	},
	bag_size(frm, cdt, cdn) {
		_compute_row_weight(frm, cdt, cdn);
	},
});

function _compute_row_weight(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const weight = flt(row.quantity) * flt(row.bag_size);
	frappe.model.set_value(cdt, cdn, "weight_kg", weight);
	_compute_total(frm);
}

function _compute_total(frm) {
	let total_kg = 0;
	let total_bags = 0;
	(frm.doc.table_ovaz || []).forEach((row) => {
		total_kg += flt(row.weight_kg);
		total_bags += cint(row.quantity);
	});
	frm.set_value("total_quantity_kg", total_kg);
	frm.set_value("total_bags", total_bags);
	if (frm.doc.price_per_kg) {
		frm.set_value("total_value", total_kg * flt(frm.doc.price_per_kg));
	}
}

function flt(v) {
	return parseFloat(v) || 0;
}
function cint(v) {
	return parseInt(v) || 0;
}
