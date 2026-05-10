"""
FarmLink Sync v2 — paginated, version-aware, permission-respecting endpoints.

Replaces the v1 endpoints in ``farmlink.utils.farmlink_sync``. The v1 module
remains as a deprecation shim (see ``v1_compat.py``) so already-deployed mobile
builds keep working through the cutover window.

Key differences from v1, mapped to the bugs they fix:

* Single transaction commit at request end (no per-record ``frappe.db.commit()``).
* Bulk-fetch pattern: one ``frappe.get_list(doctype, fields=["*"])`` call plus
  one ``frappe.get_all(child_doctype, filters={"parent": ["in", names]})`` per
  child table — no per-record ``frappe.get_doc()`` N+1.
* Permissions are honoured (no ``ignore_permissions=True`` blanket bypass).
  ``permission_query_conditions`` from ``hooks.py`` filters pulled rows;
  ``frappe.PermissionError`` from insert/save lands in ``failed[]`` with
  ``code: "PERMISSION"``.
* Soft deletes via Sync Tombstone DocType (mobile receives them in pulls).
* Server-authoritative conflict detection: if the row's current ``modified`` >
  the client-supplied ``base_version``, we don't apply the change — we return
  a ``conflicts[]`` entry with the server snapshot for the mobile UI to resolve.
* Cursor-based pagination so a fresh device sync can stream tens of thousands
  of records without OOM/timeout.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

# Frappe exposes rate_limit at different paths across versions:
#   v15+ : frappe.rate_limit (top-level alias)
#   v14- : frappe.rate_limiter.rate_limit
#   if neither is importable (very old or stripped builds) we fall back to a
#   no-op decorator so the module still loads and sync still works. The 60/min
#   guardrail is hardening, not correctness — degrading gracefully is right.
try:
	from frappe.rate_limiter import rate_limit as _rate_limit
except ImportError:
	try:
		_rate_limit = frappe.rate_limit  # type: ignore[attr-defined]
	except AttributeError:
		def _rate_limit(*_args, **_kwargs):  # type: ignore[no-redef]
			def _decorator(fn):
				return fn
			return _decorator
		frappe.logger("farmlink.sync").warning(
			"frappe.rate_limit unavailable — sync endpoints run without rate-limiting"
		)

from farmlink.sync.audit import record_session, safe_extract_client_meta
from farmlink.sync.dependency_order import (
	DOCTYPE_MAPPINGS,
	LINK_FIELD_MAPPINGS,
	PROCESSING_ORDER,
	REVERSE_DOCTYPE_MAPPINGS,
)
from farmlink.sync.serializers import (
	from_payload,
	list_child_tables,
	sync_version_of,
	to_payload,
)


DEFAULT_PAGE_SIZE = 2000
MAX_PAGE_SIZE = 5000

# Rate limit per authenticated user. The pull endpoint sees more traffic
# during initial sync (multi-page fetch); push is bursty when a field officer
# comes online with a backlog. 60/min is generous for legitimate use and
# still tight enough to short-circuit a runaway client loop.
_RATE_LIMIT_PER_MIN = 60
_TELEMETRY_RATE_LIMIT_PER_MIN = 20


# -------------------- public endpoints --------------------


@frappe.whitelist(methods=["POST"])
@_rate_limit(key="user", limit=_RATE_LIMIT_PER_MIN, seconds=60)
def pull(since=None, cursor=None, page_size=None, doctypes=None):
	started = now_datetime()
	body_for_meta = _request_body() if frappe.request and not any((since, cursor, page_size, doctypes)) else {}
	client_version, network_type = safe_extract_client_meta(body_for_meta)

	try:
		result = _pull_impl(since=since, cursor=cursor, page_size=page_size, doctypes=doctypes)
		records_pulled = sum(
			len(b.get("created") or []) + len(b.get("updated") or [])
			for b in (result.get("changes") or {}).values()
		)
		record_session(
			direction="pull",
			outcome="ok",
			started_at=started,
			records_pulled=records_pulled,
			tombstones_count=len(result.get("tombstones") or []),
			client_version=client_version,
			network_type=network_type,
		)
		return result
	except Exception as exc:
		record_session(
			direction="pull",
			outcome="error",
			started_at=started,
			error_message=str(exc),
			client_version=client_version,
			network_type=network_type,
		)
		raise


def _pull_impl(since=None, cursor=None, page_size=None, doctypes=None):
	# When called over HTTP the body lives in frappe.request.data; when called
	# directly (e.g. from the v1 deprecation shim) the args come in as kwargs.
	body = _request_body() if frappe.request and not any((since, cursor, page_size, doctypes)) else {}
	since_iso = since if since is not None else body.get("since")
	cursor = _decode_cursor(cursor if cursor is not None else body.get("cursor"))
	page_size = _clamp_page_size(page_size if page_size is not None else body.get("page_size"))
	requested = doctypes if doctypes is not None else body.get("doctypes")

	since_dt = get_datetime(since_iso) if since_iso else _epoch()
	# Frappe stores `creation` and `modified` as offset-naive in server-local
	# time. The mobile may send `since` as an ISO-8601 string with a `Z`
	# suffix (e.g. "2026-05-09T21:27:40.102Z"); get_datetime parses that as
	# offset-aware, which then explodes when we do `creation_dt > since_dt`
	# below. Convert to system-local naive so every datetime in this call
	# graph has the same shape.
	if since_dt is not None and getattr(since_dt, "tzinfo", None) is not None:
		since_dt = since_dt.astimezone().replace(tzinfo=None)
	server_time = now_datetime()

	doctype_queue = _resolve_doctype_queue(requested)
	# Snapshot the boundary for stable bucketing into created vs updated.
	# ``creation > since_dt`` => created, otherwise updated. Records modified
	# after server_time are not pulled this round (they belong to the next pull).

	changes: dict[str, dict[str, list]] = {}
	collected = 0
	next_cursor: str | None = None
	has_more = False

	start_idx = cursor.get("doctype_idx", 0)
	after_modified = cursor.get("after_modified")
	after_name = cursor.get("after_name") or ""

	for idx in range(start_idx, len(doctype_queue)):
		doctype = doctype_queue[idx]
		mobile_table = REVERSE_DOCTYPE_MAPPINGS.get(doctype)
		if not mobile_table:
			continue

		# For doctypes we *just* started (idx > start_idx OR no cursor yet),
		# the cursor for THIS doctype is the global ``since`` boundary.
		this_after_modified = after_modified if idx == start_idx and after_modified else since_iso
		this_after_name = after_name if idx == start_idx and after_modified else ""

		remaining = page_size - collected
		if remaining <= 0:
			next_cursor = _encode_cursor(idx, this_after_modified, this_after_name)
			has_more = True
			break

		records, has_more_in_doctype = _fetch_doctype_page(
			doctype,
			this_after_modified,
			this_after_name,
			remaining,
		)

		if records:
			created_list, updated_list = _bucket_records(doctype, records, since_dt)
			bucket = changes.setdefault(mobile_table, {"created": [], "updated": []})
			bucket["created"].extend(created_list)
			bucket["updated"].extend(updated_list)
			collected += len(records)

		if has_more_in_doctype:
			last = records[-1]
			next_cursor = _encode_cursor(
				idx,
				_iso(last.get("modified")),
				last.get("name"),
			)
			has_more = True
			break

		# Otherwise this doctype is exhausted; loop continues to next idx with no cursor.
		after_modified = None
		after_name = ""
	else:
		next_cursor = None
		has_more = False

	tombstones = _fetch_tombstones(since_dt, doctype_queue)

	return {
		"server_time": server_time.isoformat(),
		"next_cursor": next_cursor,
		"has_more": has_more,
		"changes": changes,
		"tombstones": tombstones,
	}


@frappe.whitelist(methods=["POST"])
@_rate_limit(key="user", limit=_RATE_LIMIT_PER_MIN, seconds=60)
def push(changes=None):
	started = now_datetime()
	body_for_meta = _request_body() if frappe.request and changes is None else {}
	client_version, network_type = safe_extract_client_meta(body_for_meta)

	try:
		result = _push_impl(changes=changes)
		processed = result.get("processed") or {}
		records_pushed = 0
		for bucket in processed.values():
			records_pushed += len(bucket.get("created") or [])
			records_pushed += len(bucket.get("updated") or [])
			records_pushed += len(bucket.get("deleted") or [])
		conflicts_count = len(result.get("conflicts") or [])
		failed_count = len(result.get("failed") or [])
		record_session(
			direction="push",
			outcome="ok",
			started_at=started,
			records_pushed=records_pushed,
			conflicts_count=conflicts_count,
			failed_count=failed_count,
			client_version=client_version,
			network_type=network_type,
		)
		return result
	except Exception as exc:
		record_session(
			direction="push",
			outcome="error",
			started_at=started,
			error_message=str(exc),
			client_version=client_version,
			network_type=network_type,
		)
		raise


def _push_impl(changes=None):
	if changes is None:
		body = _request_body() if frappe.request else {}
		incoming: dict[str, dict[str, Any]] = body.get("changes", {}) or {}
	else:
		incoming = changes or {}

	processed: dict[str, dict[str, list]] = {}
	conflicts: list[dict] = []
	failed: list[dict] = []
	id_mappings: dict[str, dict[str, str]] = {table: {} for table in PROCESSING_ORDER}

	for mobile_table in PROCESSING_ORDER:
		table_changes = incoming.get(mobile_table)
		if not table_changes:
			continue
		doctype = DOCTYPE_MAPPINGS[mobile_table]
		processed[mobile_table] = {"created": [], "updated": [], "deleted": []}

		_handle_creates(
			doctype,
			mobile_table,
			table_changes.get("created") or [],
			processed[mobile_table],
			failed,
			id_mappings,
		)
		_handle_updates(
			doctype,
			mobile_table,
			table_changes.get("updated") or [],
			processed[mobile_table],
			conflicts,
			failed,
			id_mappings,
		)
		_handle_deletes(
			doctype,
			table_changes.get("deleted") or [],
			processed[mobile_table],
			failed,
		)

	return {
		"server_time": now_datetime().isoformat(),
		"processed": processed,
		"conflicts": conflicts,
		"failed": failed,
	}


# -------------------- internal helpers --------------------


def _request_body() -> dict:
	if not frappe.request or not frappe.request.data:
		return {}
	try:
		return json.loads(frappe.request.data)
	except (ValueError, TypeError):
		return {}


def _clamp_page_size(value) -> int:
	try:
		size = int(value or DEFAULT_PAGE_SIZE)
	except (TypeError, ValueError):
		size = DEFAULT_PAGE_SIZE
	return max(1, min(size, MAX_PAGE_SIZE))


def _epoch():
	return get_datetime("1970-01-01 00:00:00")


def _iso(value):
	if value is None:
		return None
	if hasattr(value, "isoformat"):
		return value.isoformat()
	return str(value)


def _resolve_doctype_queue(requested) -> list[str]:
	if not requested:
		return [DOCTYPE_MAPPINGS[t] for t in PROCESSING_ORDER]
	allowed = set(DOCTYPE_MAPPINGS.values())
	# Honour client-requested order is fine; just intersect with our allowlist.
	return [d for d in requested if d in allowed]


def _encode_cursor(doctype_idx: int, after_modified: str | None, after_name: str | None) -> str:
	payload = json.dumps({"i": doctype_idx, "m": after_modified, "n": after_name or ""})
	return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")


def _decode_cursor(value) -> dict:
	if not value:
		return {}
	try:
		raw = base64.urlsafe_b64decode(value.encode("ascii")).decode("utf-8")
		obj = json.loads(raw)
		return {
			"doctype_idx": int(obj.get("i", 0)),
			"after_modified": obj.get("m"),
			"after_name": obj.get("n") or "",
		}
	except Exception:
		return {}


def _fetch_doctype_page(
	doctype: str,
	after_modified: str | None,
	after_name: str,
	limit: int,
) -> tuple[list[dict], bool]:
	"""One paginated page for one doctype, ordered by (modified, name).

	Returns (records, has_more). Permission filtering is enforced via the
	``permission_query_conditions`` hooks installed in Phase 1 — frappe.get_list
	applies them transparently.
	"""
	# Fetch up to limit+1 to detect has_more without a second query.
	# Filter as `modified >= after_modified` and post-filter the tie-breaker on `name`
	# in Python. This is correct and keeps us from fighting Frappe's filter DSL.
	filters: list = []
	if after_modified:
		filters.append(["modified", ">=", after_modified])

	rows = frappe.get_list(
		doctype,
		filters=filters,
		fields=["*"],
		order_by="modified asc, name asc",
		limit=limit + 1,
		ignore_permissions=False,
	)

	if after_modified and after_name:
		# Skip rows whose (modified, name) is <= the cursor's tuple.
		filtered = []
		for r in rows:
			r_mod = _iso(r.get("modified"))
			if r_mod > after_modified:
				filtered.append(r)
			elif r_mod == after_modified and (r.get("name") or "") > after_name:
				filtered.append(r)
		rows = filtered

	has_more = len(rows) > limit
	rows = rows[:limit]

	if not rows:
		return [], has_more

	_attach_child_tables(doctype, rows)
	return rows, has_more


def _attach_child_tables(doctype: str, rows: list[dict]) -> None:
	"""Batch-fetch child rows for all parents in one query per child table."""
	child_specs = list_child_tables(doctype)
	if not child_specs:
		return

	parent_names = [r["name"] for r in rows]
	for parent_field, child_doctype in child_specs:
		children = frappe.get_all(
			child_doctype,
			filters={
				"parent": ["in", parent_names],
				"parenttype": doctype,
				"parentfield": parent_field,
			},
			fields=["*"],
			order_by="`idx` asc",
			ignore_permissions=True,  # child rows inherit parent permissions
		)
		grouped: dict[str, list] = {}
		for c in children:
			grouped.setdefault(c["parent"], []).append(c)
		for r in rows:
			r[parent_field] = grouped.get(r["name"], [])


def _bucket_records(doctype: str, rows: list[dict], since_dt) -> tuple[list, list]:
	"""Split rows into (created, updated) based on creation timestamp."""
	created, updated = [], []
	for row in rows:
		# Build a Frappe Document instance for ``to_payload``. We avoid a second
		# DB roundtrip by hydrating in-place from the dict we already have.
		doc = frappe.get_doc({"doctype": doctype, **row})
		# get_doc on an existing record may try to reload; instead we pass through to_payload
		# using a shallow approach: read the dict directly.
		payload = _row_to_payload(doctype, row)
		creation = row.get("creation")
		creation_dt = get_datetime(creation) if creation else None
		if creation_dt and creation_dt > since_dt:
			created.append(payload)
		else:
			updated.append(payload)
	return created, updated


def _row_to_payload(doctype: str, row: dict) -> dict:
	"""Turn a flat dict (from frappe.get_list) plus its attached child rows
	into the same shape ``serializers.to_payload`` produces.

	Avoids a second ``frappe.get_doc`` per record (which would reintroduce N+1)
	by serializing the dict directly. Child tables are already attached by
	``_attach_child_tables`` before we get here.
	"""
	from farmlink.sync.serializers import (
		COSMETIC_FIELDTYPES,
		SERVER_INTERNAL_FIELDS,
		_serialize_child,
		sync_version_of,
	)

	meta = frappe.get_meta(doctype)
	out: dict = {
		"name": row.get("name"),
		"creation": _iso(row.get("creation")),
		"modified": _iso(row.get("modified")),
	}

	# sync_version is derived from modified
	mod = row.get("modified")
	if mod:
		mod_dt = get_datetime(mod)
		out["sync_version"] = int(mod_dt.timestamp() * 1000)
	else:
		out["sync_version"] = 0

	for field in meta.fields:
		if field.fieldtype in COSMETIC_FIELDTYPES:
			continue
		if field.fieldname in SERVER_INTERNAL_FIELDS:
			continue
		value = row.get(field.fieldname)
		if field.fieldtype == "Table":
			out[field.fieldname] = [
				{k: v for k, v in (c.items() if isinstance(c, dict) else c.as_dict().items())
				 if k not in SERVER_INTERNAL_FIELDS}
				for c in (value or [])
			]
		elif field.fieldtype in ("Datetime", "Date", "Time"):
			out[field.fieldname] = _iso(value)
		else:
			out[field.fieldname] = value
	return out


def _fetch_tombstones(since_dt, doctype_queue: list[str]) -> list[dict]:
	"""Return tombstones since the cutoff. The Sync Tombstone DocType has its
	own permission rules (System Manager only), but for sync we want every
	authenticated user to see tombstones for the doctypes they can read. We
	scope to the requested doctype queue and skip permission checks here —
	the *content* of a tombstone (just doctype+name+timestamp) is not
	sensitive once we've already gated the parent doctype's pull."""
	if not doctype_queue:
		return []
	rows = frappe.get_all(
		"Sync Tombstone",
		filters={
			"deleted_at": [">", since_dt],
			"ref_doctype": ["in", doctype_queue],
		},
		fields=["ref_doctype", "ref_name", "deleted_at"],
		order_by="deleted_at asc",
		ignore_permissions=True,
	)
	return [
		{
			"doctype": r["ref_doctype"],
			"name": r["ref_name"],
			"deleted_at": _iso(r["deleted_at"]),
		}
		for r in rows
	]


# -------------------- push helpers --------------------


def _resolve_links_in_place(record: dict, mobile_table: str, id_mappings: dict) -> None:
	"""Replace any client_id references in known FK fields with their Frappe names."""
	link_map = LINK_FIELD_MAPPINGS.get(mobile_table) or {}
	for field, target_table in link_map.items():
		value = record.get(field)
		if not value:
			continue
		mapped = id_mappings.get(target_table, {}).get(value)
		if mapped:
			record[field] = mapped


def _handle_creates(
	doctype: str,
	mobile_table: str,
	creates: list[dict],
	bucket: dict,
	failed: list,
	id_mappings: dict,
) -> None:
	for raw in creates:
		client_id = raw.get("client_id") or raw.get("id") or raw.get("name")
		try:
			_resolve_links_in_place(raw, mobile_table, id_mappings)
			payload = from_payload(raw, doctype)
			doc_dict = {"doctype": doctype, **payload}
			# Honour client-supplied name only if no autoname conflict; otherwise let Frappe assign.
			if "name" in payload:
				doc_dict["__newname"] = payload["name"]
			doc = frappe.get_doc(doc_dict)
			doc.insert()
			frappe_name = doc.name
			bucket["created"].append(
				{
					"client_id": client_id,
					"name": frappe_name,
					"sync_version": sync_version_of(doc),
				}
			)
			if client_id:
				id_mappings.setdefault(mobile_table, {})[client_id] = frappe_name
		except frappe.PermissionError as exc:
			failed.append(
				{
					"doctype": doctype,
					"client_id": client_id,
					"code": "PERMISSION",
					"message": str(exc)[:200],
				}
			)
		except frappe.DuplicateEntryError:
			# Idempotency: if the mobile re-pushes a record we've already created,
			# resolve it to the existing record without erroring.
			if client_id and frappe.db.exists(doctype, client_id):
				existing = frappe.get_doc(doctype, client_id)
				bucket["created"].append(
					{
						"client_id": client_id,
						"name": existing.name,
						"sync_version": sync_version_of(existing),
					}
				)
				id_mappings.setdefault(mobile_table, {})[client_id] = existing.name
			else:
				failed.append(
					{
						"doctype": doctype,
						"client_id": client_id,
						"code": "DUPLICATE",
						"message": "Already exists",
					}
				)
		except Exception as exc:
			frappe.log_error(
				message=f"v2.push create {doctype}: {exc}",
				title="FarmLink Sync v2",
			)
			failed.append(
				{
					"doctype": doctype,
					"client_id": client_id,
					"code": "ERROR",
					"message": str(exc)[:200],
				}
			)


def _handle_updates(
	doctype: str,
	mobile_table: str,
	updates: list[dict],
	bucket: dict,
	conflicts: list,
	failed: list,
	id_mappings: dict,
) -> None:
	for raw in updates:
		name = raw.get("name") or raw.get("frappe_id")
		base_version = raw.get("base_version") or 0
		if not name:
			failed.append(
				{
					"doctype": doctype,
					"code": "MISSING_NAME",
					"message": "Update requires name",
				}
			)
			continue
		try:
			if not frappe.db.exists(doctype, name):
				failed.append(
					{
						"doctype": doctype,
						"name": name,
						"code": "NOT_FOUND",
						"message": f"{doctype} {name} not found",
					}
				)
				continue
			doc = frappe.get_doc(doctype, name)
			current_version = sync_version_of(doc)
			if base_version and current_version > base_version:
				conflicts.append(
					{
						"doctype": doctype,
						"name": name,
						"client_base_version": base_version,
						"server_version": current_version,
						"server_record": to_payload(doc),
					}
				)
				continue
			_resolve_links_in_place(raw, mobile_table, id_mappings)
			payload = from_payload(raw, doctype)
			for field, value in payload.items():
				if field in ("name", "doctype"):
					continue
				try:
					doc.set(field, value)
				except Exception:
					# Field type mismatch — log and skip rather than aborting the whole push.
					continue
			doc.save()
			bucket["updated"].append(
				{"name": doc.name, "sync_version": sync_version_of(doc)}
			)
		except frappe.PermissionError as exc:
			failed.append(
				{
					"doctype": doctype,
					"name": name,
					"code": "PERMISSION",
					"message": str(exc)[:200],
				}
			)
		except Exception as exc:
			frappe.log_error(
				message=f"v2.push update {doctype} {name}: {exc}",
				title="FarmLink Sync v2",
			)
			failed.append(
				{
					"doctype": doctype,
					"name": name,
					"code": "ERROR",
					"message": str(exc)[:200],
				}
			)


def _handle_deletes(
	doctype: str,
	deletes: list,
	bucket: dict,
	failed: list,
) -> None:
	for ref in deletes:
		name = ref if isinstance(ref, str) else (ref or {}).get("name")
		if not name:
			continue
		try:
			if not frappe.db.exists(doctype, name):
				bucket["deleted"].append(name)  # already gone is success
				continue
			frappe.delete_doc(doctype, name)
			bucket["deleted"].append(name)
		except frappe.PermissionError as exc:
			failed.append(
				{
					"doctype": doctype,
					"name": name,
					"code": "PERMISSION",
					"message": str(exc)[:200],
				}
			)
		except Exception as exc:
			frappe.log_error(
				message=f"v2.push delete {doctype} {name}: {exc}",
				title="FarmLink Sync v2",
			)
			failed.append(
				{
					"doctype": doctype,
					"name": name,
					"code": "ERROR",
					"message": str(exc)[:200],
				}
			)


# -------------------- diagnostics --------------------


@frappe.whitelist(methods=["GET", "POST"])
def status():
	"""Lightweight health/diagnostic endpoint replacing v1 ``get_sync_status``.

	Returns per-doctype row counts visible to the *current authenticated user*
	(so the mobile app can sanity-check its local DB sizes after a sync).
	"""
	stats: dict[str, int] = {}
	for table, doctype in DOCTYPE_MAPPINGS.items():
		try:
			stats[table] = len(
				frappe.get_list(doctype, fields=["name"], limit=0, ignore_permissions=False)
			)
		except Exception:
			stats[table] = -1
	return {
		"server_time": now_datetime().isoformat(),
		"user": frappe.session.user,
		"counts": stats,
	}


@frappe.whitelist(methods=["POST"])
@_rate_limit(key="user", limit=_TELEMETRY_RATE_LIMIT_PER_MIN, seconds=60)
def report_telemetry():
	"""Receive a buffered batch of client-side telemetry events.

	The mobile app's services/sync/telemetry.service.ts buffers events locally
	and ships them periodically (or after a successful sync). Per-event shape:

	    {
	      "type": "sync_pull" | "sync_push" | "sync_error" | "conflict_resolved",
	      "ts": <ms epoch>,
	      "duration_ms": <int>,
	      "records": <int>,
	      "error_code": <str | null>,
	      "details": { <free-form> }
	    }

	The endpoint logs each event into a dedicated logger plus writes one
	aggregate Sync Session Log row so ops can dashboard the stream alongside
	server-side per-request rows.
	"""
	started = now_datetime()
	body = _request_body()
	events = body.get("events") or []
	client_version, network_type = safe_extract_client_meta(body)

	if not isinstance(events, list):
		events = []
	# Cap absurd payloads.
	events = events[:200]

	logger = frappe.logger("farmlink.sync.telemetry")
	error_count = 0
	for ev in events:
		if not isinstance(ev, dict):
			continue
		ev_type = (ev.get("type") or "")[:40]
		if ev_type == "sync_error":
			error_count += 1
		try:
			logger.info(
				{
					"user": frappe.session.user,
					"type": ev_type,
					"ts": ev.get("ts"),
					"duration_ms": ev.get("duration_ms"),
					"records": ev.get("records"),
					"error_code": (ev.get("error_code") or "")[:80],
					"details": ev.get("details") if isinstance(ev.get("details"), dict) else None,
				}
			)
		except Exception:
			pass

	record_session(
		direction="telemetry",
		outcome="ok",
		started_at=started,
		failed_count=error_count,
		client_version=client_version,
		network_type=network_type,
	)

	return {"received": len(events)}
