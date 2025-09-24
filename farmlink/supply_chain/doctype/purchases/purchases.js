// purchases.js — Client Script for "Purchases"
// Option A: open a prefilled Payment (no server insert)

// ---------- helpers ----------
function flt_safe(v) { return flt(v || 0); }

function calculate_total(frm) {
  var rate = flt_safe(frm.doc.price_rate_of_the_day);
  var kg   = flt_safe(frm.doc.weight_in_kg);
  frm.set_value('total_price', rate * kg);
}

// simple debounce (no modern syntax)
function debounce(fn, wait) {
  var t = null;
  return function() {
    var ctx = this, args = arguments;
    clearTimeout(t);
    t = setTimeout(function(){ fn.apply(ctx, args); }, wait);
  };
}

function attach_live_handlers(frm) {
  try {
    var recalc = debounce(function(){ calculate_total(frm); }, 50);
    ['price_rate_of_the_day', 'weight_in_kg'].forEach(function(fname){
      var f = frm.get_field(fname);
      if (f && f.$input) {
        // prevent duplicate bindings across refreshes
        f.$input.off('input.calc').on('input.calc', recalc);
        f.$input.off('keyup.calc').on('keyup.calc', recalc);
      }
    });
  } catch (e) {
    console.error('attach_live_handlers error:', e);
  }
}

function set_header_indicator(frm, summary) {
  if (!frm.dashboard || !summary || !summary.status) return;
  var color = (summary.status === "Paid") ? "green"
           : (summary.status === "Partially Paid") ? "orange"
           : "red";
  try {
    if (frm.dashboard.clear_headline) frm.dashboard.clear_headline();
    if (frm.dashboard.add_indicator) {
      frm.dashboard.add_indicator(
        summary.status + ": Paid " + (summary.paid || 0) + " / Total " + (summary.total || 0),
        color
      );
    }
  } catch (e) {
    console.warn('indicator issue:', e);
  }
}

// Open a new Payment with defaults (user will pick Mode of Payment & submit)
function create_payment(frm) {
  // re-check right now to avoid racing with other users' payments
  frappe.call({
    method: "farmlink.api.get_payment_summary",
    args: { purchase_name: frm.doc.name },
    freeze: true,
    callback: function(r) {
      var s = (r && r.message) || { outstanding: 0 };
      if (!s.outstanding || s.outstanding <= 0) {
        frappe.msgprint("This Purchase is already fully paid.");
        return;
      }

      // Prefill Payment; user can edit payment_amount or MoP before submit
      frappe.route_options = {
        purchase_invoice: frm.doc.name,
        // show the purchase context on the Payment form
        purchase_amount: frm.doc.total_price,   // align Payment.fetch_from if you use it
        outstanding_amount: s.outstanding,
        // suggest paying the full outstanding; user may change it
        payment_amount: s.outstanding
      };
      frappe.new_doc("Payment");
    }
  });
}

// ---------- main ----------
frappe.ui.form.on('Purchases', {
  onload_post_render: function(frm) {
    attach_live_handlers(frm);
  },

  // keep total updated on normal field change too
  price_rate_of_the_day: function(frm) { calculate_total(frm); },
  weight_in_kg:          function(frm) { calculate_total(frm); },

  refresh: function(frm) {
    // 1) read-only safety for phone fields (if present)
    if (frm.get_field('phone'))            frm.set_df_property('phone', 'read_only', 1);
    if (frm.get_field('suppliers_phone'))  frm.set_df_property('suppliers_phone', 'read_only', 1);

    // 2) always ensure total is correct
    calculate_total(frm);

    // 3) show payment summary + button only for saved docs
    if (frm.is_new()) return;

    frappe.call({
      method: "farmlink.api.get_payment_summary",
      args: { purchase_name: frm.doc.name },
      callback: function(r) {
        var s = (r && r.message) || { total: 0, paid: 0, outstanding: 0, status: "Unpaid" };

        // header indicator
        set_header_indicator(frm, s);

        // show Create Payment only if there is outstanding amount
        try {
          if (frm.clear_custom_buttons) frm.clear_custom_buttons();
          if (s.outstanding > 0 && frm.add_custom_button) {
            frm.add_custom_button(__('Create Payment'), function() {
              create_payment(frm);
            });
          }
        } catch (e) {
          console.warn('buttons issue:', e);
        }
      }
    });
  },

  // If you had a DocType > Actions row wired as "Route" or "Server Action" you may not need this,
  // but if you DID add an Action (JS) named "create_payment", this will be called:
  create_payment: function(frm) { create_payment(frm); },

  // ----- phone cleanup when links change -----
  farmer: function(frm) {
    // if farmer cleared, make sure phone clears (fetch_from may not clear automatically)
    if (!frm.doc.farmer && frm.doc.phone) frm.set_value('phone', '');
  },

  supplier: function(frm) {
    if (!frm.doc.supplier && frm.doc.suppliers_phone) frm.set_value('suppliers_phone', '');
  },

  // ----- purchase type–aware cleanup -----
  // Direct:        Farmer only -> clear Supplier + supplier phone
  // Bulk Supplier: Supplier only -> clear Farmer + farmer phone
  // Farmer Supplier: both allowed -> clear missing party phones only
  purchase_type: function(frm) {
    var pt = frm.doc.purchase_type;
    if (pt === 'Direct') {
      if (frm.doc.supplier) frm.set_value('supplier', null);
      if (frm.doc.suppliers_phone) frm.set_value('suppliers_phone', '');
      if (!frm.doc.farmer && frm.doc.phone) frm.set_value('phone', '');
    } else if (pt === 'Bulk Supplier') {
      if (frm.doc.farmer) frm.set_value('farmer', null);
      if (frm.doc.phone) frm.set_value('phone', '');
      if (!frm.doc.supplier && frm.doc.suppliers_phone) frm.set_value('suppliers_phone', '');
    } else if (pt === 'Farmer Supplier') {
      if (!frm.doc.farmer && frm.doc.phone) frm.set_value('phone', '');
      if (!frm.doc.supplier && frm.doc.suppliers_phone) frm.set_value('suppliers_phone', '');
    }
  }
});
