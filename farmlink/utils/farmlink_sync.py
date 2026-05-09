"""
DEPRECATED — superseded by ``farmlink.sync.v2``.

These endpoints remain only so that already-deployed mobile builds (which call
``/api/method/farmlink.utils.farmlink_sync.pull_changes`` and
``.push_changes``) keep working through the cutover window. Each call:

  1. Logs a deprecation warning so we can track when v1 traffic drops to zero.
  2. Translates the v1 request into the v2 input shape.
  3. Delegates to ``farmlink.sync.v2`` internals.
  4. Reshapes the v2 response back into the v1 shape the mobile expects.

Once telemetry shows zero v1 traffic for 7 consecutive days, this module can be
deleted (planned in Phase 6 cutover).

The v1 module previously held all of the buggy logic the v2 module replaces:
  - undefined FIELD_MAPPINGS reference (would crash if reached)
  - washing_stations / centers naming mismatch in LINK_FIELD_MAPPINGS
  - per-record frappe.db.commit() inside loops (one txn per row)
  - N+1 frappe.get_doc loop after frappe.get_all
  - blanket ignore_permissions=True bypassing all DocType perms
  - no soft-delete propagation
  - no conflict detection

All of those are fixed in farmlink.sync.v2 and stay fixed even when the v1 shim
forwards calls.
"""

import json
from datetime import datetime

import frappe
from frappe.utils import now_datetime

from farmlink.sync import v2
from farmlink.sync.dependency_order import (
	DOCTYPE_MAPPINGS,
	REVERSE_DOCTYPE_MAPPINGS,
)


_V1_PAGE_SAFETY_CAP = 50_000
_V1_PER_PULL_PAGE_SIZE = 5_000


_V1_COUNTER_TTL_SECONDS = 60 * 60 * 24 * 32  # ~32 days, just past the 7-day quiet-period


def _warn_deprecated(endpoint: str) -> None:
	"""Per-call breadcrumb the cutover dashboard uses to know when v1 dies.

	Bumps a daily cache counter (resets after ~32 days) so ops can run::

	    bench --site <site> execute farmlink.utils.farmlink_sync.v1_call_summary

	to see how much v1 traffic remains. When the counter reads 0 for 7
	consecutive days the shim can be deleted.
	"""
	user = frappe.session.user
	frappe.logger("farmlink.sync.v1_deprecation").warning(
		f"DEPRECATED v1 sync endpoint called: {endpoint} (user={user})"
	)
	try:
		today = now_datetime().strftime("%Y-%m-%d")
		cache_key = f"farmlink:v1_calls:{today}:{endpoint}"
		current = frappe.cache.get_value(cache_key) or 0
		frappe.cache.set_value(
			cache_key,
			int(current) + 1,
			expires_in_sec=_V1_COUNTER_TTL_SECONDS,
		)
	except Exception:
		# Counter is best-effort observability; never let it break the request.
		pass


@frappe.whitelist()
def v1_call_summary():
	"""Return the per-day v1 call counts for the last 30 days. System Manager only."""
	if "System Manager" not in frappe.get_roles(frappe.session.user):
		frappe.throw("Not allowed", frappe.PermissionError)
	from datetime import timedelta

	today = now_datetime().date()
	rows = []
	for offset in range(0, 30):
		day = today - timedelta(days=offset)
		day_str = day.isoformat()
		entry = {"date": day_str}
		for endpoint in ("pull_changes", "push_changes", "get_sync_status"):
			cache_key = f"farmlink:v1_calls:{day_str}:{endpoint}"
			try:
				entry[endpoint] = int(frappe.cache.get_value(cache_key) or 0)
			except Exception:
				entry[endpoint] = -1
		rows.append(entry)
	return rows


def _v1_request_body() -> dict:
	if not frappe.request or not frappe.request.data:
		return {}
	try:
		return json.loads(frappe.request.data)
	except (ValueError, TypeError):
		return {}


def _ms_to_iso(timestamp_ms) -> str | None:
	if not timestamp_ms:
		return None
	try:
		return datetime.fromtimestamp(int(timestamp_ms) / 1000).isoformat()
	except (TypeError, ValueError):
		return None


@frappe.whitelist(methods=["POST", "GET"])
def pull_changes():
	"""DEPRECATED v1 pull. Forwards to farmlink.sync.v2.pull and reshapes."""
	_warn_deprecated("pull_changes")

	body = _v1_request_body()
	since_iso = _ms_to_iso(body.get("last_sync_timestamp"))

	v1_changes: dict[str, dict[str, list]] = {
		mobile: {"created": [], "updated": [], "deleted": []}
		for mobile in DOCTYPE_MAPPINGS
	}
	cursor = None
	collected = 0

	while True:
		response = v2.pull(
			since=since_iso,
			cursor=cursor,
			page_size=_V1_PER_PULL_PAGE_SIZE,
		)
		for mobile_table, bucket in (response.get("changes") or {}).items():
			target = v1_changes.setdefault(
				mobile_table, {"created": [], "updated": [], "deleted": []}
			)
			target["created"].extend(bucket.get("created") or [])
			target["updated"].extend(bucket.get("updated") or [])
			collected += len(bucket.get("created") or []) + len(bucket.get("updated") or [])

		# Distribute tombstones back into v1's per-doctype `deleted` arrays.
		for tomb in response.get("tombstones") or []:
			doctype = tomb.get("doctype")
			mobile_table = REVERSE_DOCTYPE_MAPPINGS.get(doctype)
			if mobile_table:
				v1_changes.setdefault(
					mobile_table, {"created": [], "updated": [], "deleted": []}
				)["deleted"].append(tomb.get("name"))

		cursor = response.get("next_cursor")
		if not response.get("has_more") or not cursor:
			break
		if collected >= _V1_PAGE_SAFETY_CAP:
			frappe.logger().warning(
				"[FarmLink] v1 pull_changes hit safety cap %s; remaining records will require v2 client",
				_V1_PAGE_SAFETY_CAP,
			)
			break

	return {
		"changes": v1_changes,
		"timestamp": int(now_datetime().timestamp() * 1000),
	}


@frappe.whitelist(methods=["POST"])
def push_changes():
	"""DEPRECATED v1 push. Forwards to farmlink.sync.v2.push and reshapes."""
	_warn_deprecated("push_changes")

	body = _v1_request_body()
	incoming = body.get("changes", {}) or {}

	response = v2.push(changes=incoming)

	# v1 shape merged conflicts and failures into a single 'failed' array per
	# table, plus a top-level id_mappings dict. Recompose that.
	processed: dict[str, dict] = {}
	id_mappings: dict[str, dict[str, str]] = {}

	for mobile_table, bucket in (response.get("processed") or {}).items():
		processed[mobile_table] = {
			"created": [],
			"updated": [],
			"deleted": list(bucket.get("deleted") or []),
			"failed": [],
		}
		for created in bucket.get("created") or []:
			processed[mobile_table]["created"].append(
				{
					"watermelon_id": created.get("client_id"),
					"frappe_name": created.get("name"),
				}
			)
			if created.get("client_id") and created.get("name"):
				id_mappings.setdefault(mobile_table, {})[created["client_id"]] = created["name"]
		for updated in bucket.get("updated") or []:
			processed[mobile_table]["updated"].append(updated.get("name"))

	for conflict in response.get("conflicts") or []:
		mobile_table = REVERSE_DOCTYPE_MAPPINGS.get(conflict.get("doctype"))
		if not mobile_table:
			continue
		processed.setdefault(
			mobile_table, {"created": [], "updated": [], "deleted": [], "failed": []}
		)["failed"].append(
			{
				"id": conflict.get("name"),
				"operation": "update",
				"error": "version conflict (client_base_version older than server_version)",
			}
		)

	for failure in response.get("failed") or []:
		mobile_table = REVERSE_DOCTYPE_MAPPINGS.get(failure.get("doctype"))
		if not mobile_table:
			continue
		processed.setdefault(
			mobile_table, {"created": [], "updated": [], "deleted": [], "failed": []}
		)["failed"].append(
			{
				"id": failure.get("client_id") or failure.get("name") or "unknown",
				"operation": "create",
				"error": f"[{failure.get('code')}] {failure.get('message')}",
			}
		)

	return {
		"status": "success",
		"message": "Changes pushed via v2 (v1 shim active)",
		"processed": processed,
		"id_mappings": id_mappings,
		"timestamp": int(now_datetime().timestamp() * 1000),
	}


@frappe.whitelist(methods=["GET", "POST"])
def get_sync_status():
	"""DEPRECATED v1 status. Forwards to farmlink.sync.v2.status."""
	_warn_deprecated("get_sync_status")
	v2_status = v2.status()
	# v1 callers expected {"status": "ready", "statistics": {table: count}, "server_time": ms}
	return {
		"status": "ready",
		"statistics": v2_status.get("counts", {}),
		"server_time": int(now_datetime().timestamp() * 1000),
	}
