// Hide "Submit" until status === "Completed" and the doc is clean.
// Keep Save working at all times, and use savesubmit() for the action.

frappe.ui.form.on('Primary Processing', {
  refresh(frm) { defer(() => update_actions(frm)); },
  onload_post_render(frm) { defer(() => update_actions(frm)); },
  status(frm) { defer(() => update_actions(frm)); },
  after_save(frm) { defer(() => update_actions(frm)); },
  // also listen to dirty-state changes across versions
  dirty_change(frm) { defer(() => update_actions(frm)); }
});

function defer(cb) { setTimeout(cb, 0); }

function update_actions(frm) {
  const isDraft     = frm.doc.docstatus === 0;
  const isSaved     = !frm.is_new();
  const isDirty     = !!frm.is_dirty?.();
  const isCompleted = (frm.doc.status || "").toLowerCase() === "completed";

  // Only allow submit when draft, saved, clean, and Completed
  const canSubmit   = isDraft && isSaved && !isDirty && isCompleted;

  // Primary action: Save when can't submit; Submit when we can
  if (frm.page?.set_primary_action) {
    if (canSubmit) {
      frm.page.set_primary_action(__('Submit'), () => frm.savesubmit());
    } else {
      frm.page.set_primary_action(__('Save'), () => frm.save());
    }
  }

  // Toggle the native Submit button (if present) to mirror canSubmit
  if (frm.page?.btn_submit) {
    frm.page.btn_submit.toggle(canSubmit);
  }

  // Be defensive with any extra "Submit" entries in menus,
  // but do NOT touch .primary-action (that’s Save in draft)
  const $wrap = frm.page?.wrapper ? frm.page.wrapper : $(document);
  const submitLabel = __('Submit');

  $wrap.find('button[data-label="Submit"], a[data-label="Submit"]').toggle(canSubmit);
  if (submitLabel !== 'Submit') {
    $wrap.find(`button[data-label="${submitLabel}"], a[data-label="${submitLabel}"]`).toggle(canSubmit);
  }
}
