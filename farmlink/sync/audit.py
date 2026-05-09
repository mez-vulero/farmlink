"""
Sync Session Log writer.

Each call to farmlink.sync.v2.{pull,push,report_telemetry} ends in a
``record_session`` call that writes one row capturing:

  - Who: frappe.session.user
  - What: direction (pull / push / telemetry), outcome (ok / error / rate_limited)
  - When: started_at, finished_at, duration_ms
  - Volume: records_pulled / records_pushed / conflicts_count / failed_count / tombstones_count
  - Diagnostics: client_version, network_type (sent by the mobile when known),
    error_message (when outcome != ok)

The writer is best-effort — observability MUST NEVER break the sync request
itself, so we swallow any exception with a logger.warning. The Sync Session Log
DocType has its own permissions; we use ignore_permissions=True here because
the request user might be a Warehouse user without explicit Sync-Session-Log
write rights, but the *fact* that they made a sync call is the thing we need
to record.

Reads of the table are gated normally — only System Manager / Farmlink Manager
see the log via Desk.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import frappe
from frappe.utils import now_datetime


def record_session(
	*,
	direction: str,
	outcome: str,
	started_at: datetime | None,
	records_pulled: int = 0,
	records_pushed: int = 0,
	conflicts_count: int = 0,
	failed_count: int = 0,
	tombstones_count: int = 0,
	client_version: str | None = None,
	network_type: str | None = None,
	error_message: str | None = None,
) -> str | None:
	"""Write one Sync Session Log row. Returns the new row's name, or None on failure."""
	try:
		finished = now_datetime()
		duration_ms = 0
		if started_at:
			duration_ms = int((finished - started_at).total_seconds() * 1000)

		doc = frappe.get_doc(
			{
				"doctype": "Sync Session Log",
				"user": frappe.session.user,
				"direction": direction,
				"outcome": outcome,
				"started_at": started_at,
				"finished_at": finished,
				"duration_ms": duration_ms,
				"records_pulled": records_pulled,
				"records_pushed": records_pushed,
				"conflicts_count": conflicts_count,
				"failed_count": failed_count,
				"tombstones_count": tombstones_count,
				"client_version": (client_version or "")[:140],
				"network_type": (network_type or "")[:64],
				"error_message": (error_message or "")[:5000],
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name
	except Exception as exc:
		frappe.logger("farmlink.sync.audit").warning(
			f"record_session failed (direction={direction}): {exc}"
		)
		return None


def safe_extract_client_meta(body: dict[str, Any] | None) -> tuple[str | None, str | None]:
	"""Pull the optional ``client_meta`` envelope (version + network_type) out of a request body.

	The mobile telemetry service tags every sync request with:
		body["client_meta"] = {"version": "1.2.3", "network": "wifi"}

	If absent we just return (None, None).
	"""
	if not body or not isinstance(body, dict):
		return None, None
	meta = body.get("client_meta")
	if not isinstance(meta, dict):
		return None, None
	version = meta.get("version") if isinstance(meta.get("version"), str) else None
	network = meta.get("network") if isinstance(meta.get("network"), str) else None
	return version, network
