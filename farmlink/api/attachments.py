# Copyright (c) 2025, vulerotech and contributors
# For license information, please see license.txt
"""
Mobile attachment upload endpoint.

The mobile app keeps a local sidecar queue of files that need to land on
Frappe (farmer photo, bank book, land certificate). Once the parent farmer
row is synced and has a real Frappe `name`, the queue is flushed by POSTing
each file here as a multipart form upload.

This endpoint:
- Verifies the caller has *write* permission on the parent doctype + name
  (so the existing RBAC matrix still applies — Warehouse can't shove files
  onto purchase records etc.).
- Inspects the first few bytes ("magic bytes") to confirm the payload is
  actually one of the allowed types. We do NOT trust the client's
  Content-Type header — a relabeled binary would otherwise sail through
  Frappe's filename-extension check.
- Creates a Frappe File row via save_file(), then atomically sets the
  parent doctype's <fieldname> column to the resulting file_url in a
  single transaction. Failing the second write rolls back the first so
  we don't orphan File rows.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils.file_manager import save_file

# Per-field whitelist. Mirrors the `allowed_file_extensions` we set on the
# DocType field — having it here too means a malformed JSON config (e.g.
# allowed_file_extensions missing) can't silently widen the surface area.
FIELD_ALLOWED_TYPES: dict[tuple[str, str], frozenset[str]] = {
	("Farmers", "farmers_photo"): frozenset({"image/jpeg", "image/png"}),
	("Farmers", "bank_book"): frozenset({"image/jpeg", "image/png", "application/pdf"}),
	("Farmers", "land_ownership_certificate"): frozenset({"image/jpeg", "image/png", "application/pdf"}),
}

# Magic-byte signatures. Read just enough leading bytes to discriminate.
_MAGIC: tuple[tuple[bytes, str], ...] = (
	(b"\xff\xd8\xff", "image/jpeg"),
	(b"\x89PNG\r\n\x1a\n", "image/png"),
	(b"%PDF-", "application/pdf"),
)

# Soft size cap (bytes). Server's frappe.conf.max_file_size remains the hard
# infrastructure ceiling; this is a UX guard against accidentally enormous
# camera dumps over rural data.
MAX_BYTES = 15 * 1024 * 1024  # 15 MB


def _sniff_mime(blob: bytes) -> str | None:
	head = blob[:16]
	for signature, mime in _MAGIC:
		if head.startswith(signature):
			return mime
	return None


@frappe.whitelist()
def upload_for_field(
	doctype: str,
	name: str,
	fieldname: str,
	is_private: int = 1,
) -> dict[str, str]:
	"""Attach the request's multipart `file` to (doctype, name).(fieldname)."""
	if not doctype or not name or not fieldname:
		frappe.throw(_("doctype, name and fieldname are required"))

	allowed = FIELD_ALLOWED_TYPES.get((doctype, fieldname))
	if allowed is None:
		frappe.throw(
			_("Attachment uploads are not permitted on {0}.{1}").format(doctype, fieldname),
			frappe.PermissionError,
		)

	# Require *write* permission on the parent. Read isn't enough — we're
	# mutating the row by setting a field, so the caller must own that right.
	if not frappe.has_permission(doctype, "write", doc=name):
		frappe.throw(
			_("You do not have permission to attach files to {0} {1}").format(doctype, name),
			frappe.PermissionError,
		)

	files = frappe.request.files
	if not files or "file" not in files:
		frappe.throw(_("No file in request"))

	file_obj = files["file"]
	# Read once — Frappe's save_file wants the bytes, and we need the head for
	# the magic-byte sniff anyway.
	content = file_obj.read()
	if not content:
		frappe.throw(_("Uploaded file is empty"))
	if len(content) > MAX_BYTES:
		frappe.throw(_("File exceeds the {0} MB limit").format(MAX_BYTES // (1024 * 1024)))

	sniffed = _sniff_mime(content)
	if sniffed is None or sniffed not in allowed:
		# 415-style rejection; don't echo the (untrusted) client mime type.
		frappe.throw(
			_("File type not allowed for {0}").format(fieldname),
			frappe.ValidationError,
		)

	filename = file_obj.filename or "attachment"
	# save_file handles attached_to_* linkage, dedupes by content hash, and
	# generates a stable file_url under /files or /private/files.
	saved = save_file(
		fname=filename,
		content=content,
		dt=doctype,
		dn=name,
		decode=False,
		is_private=int(is_private),
	)

	# Atomically point the parent field at the new URL. db_set commits in the
	# same request transaction as save_file, so a downstream failure rolls
	# both back together.
	parent = frappe.get_doc(doctype, name)
	parent.db_set(fieldname, saved.file_url, update_modified=True)

	return {
		"file_url": saved.file_url,
		"file_name": saved.name,
		"fieldname": fieldname,
	}
