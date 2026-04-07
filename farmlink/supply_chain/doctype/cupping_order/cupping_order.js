const SCORE_FIELDS = [
	"fragrance_aroma", "flavor", "aftertaste", "acidity",
	"body", "balance", "uniformity", "overall",
];

frappe.ui.form.on("Cupping Order", {
	refresh(frm) {
		SCORE_FIELDS.forEach((f) => {
			frm.fields_dict[f] && frm.fields_dict[f].$input &&
				frm.fields_dict[f].$input.attr("min", 0).attr("max", 10).attr("step", 0.25);
		});
	},
});

// Auto-compute total when any score field changes
SCORE_FIELDS.forEach((field) => {
	frappe.ui.form.on("Cupping Order", field, function (frm) {
		let total = 0;
		SCORE_FIELDS.forEach((f) => { total += parseFloat(frm.doc[f]) || 0; });
		frm.set_value("total_score", total);

		let cls = "";
		if (total >= 85) cls = "Specialty";
		else if (total >= 80) cls = "Premium";
		else if (total >= 75) cls = "Commercial High";
		else if (total >= 70) cls = "Commercial";
		else cls = "Below Commercial";
		frm.set_value("cup_classification", cls);
	});
});
