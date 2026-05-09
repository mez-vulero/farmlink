"""
Per-user login endpoint for FarmLink mobile clients.

Replaces the legacy shared-API-key model. The mobile app POSTs email + password
once; the backend authenticates via Frappe's LoginManager, ensures the user has
an api_key/api_secret pair (generating one on first login), and returns the pair
together with the user's Personnel record so the mobile app gets identity + auth
in a single round trip.

Subsequent sync requests authenticate with `Authorization: token <key>:<secret>`
and never need to call this endpoint again unless the device logs out.
"""

import frappe
from frappe import _
from frappe.auth import LoginManager


@frappe.whitelist(allow_guest=True, methods=["POST"])
def login(email: str | None = None, password: str | None = None):
	if not email or not password:
		frappe.local.response["http_status_code"] = 400
		return {"error": _("Email and password are required")}

	login_manager = LoginManager()
	try:
		login_manager.authenticate(user=email, pwd=password)
		login_manager.post_login()
	except frappe.AuthenticationError:
		frappe.local.response["http_status_code"] = 401
		return {"error": _("Invalid email or password")}

	user = frappe.session.user
	api_key, api_secret = _ensure_api_credentials(user)
	personnel = _get_personnel(user)

	return {
		"api_key": api_key,
		"api_secret": api_secret,
		"user_id": user,
		"personnel": personnel,
	}


def _ensure_api_credentials(user: str) -> tuple[str, str]:
	"""Idempotently ensure the user has both api_key and api_secret.

	Frappe stores api_secret as a Password fieldtype (encrypted in __Auth).
	We can re-read it via get_password; if either half of the pair is missing
	we generate a fresh pair so the mobile app never receives a stale half.
	"""
	user_doc = frappe.get_doc("User", user)

	api_key = user_doc.api_key or None
	api_secret = None
	if api_key:
		api_secret = user_doc.get_password("api_secret", raise_exception=False)

	if not api_key or not api_secret:
		api_key = frappe.generate_hash(length=15)
		api_secret = frappe.generate_hash(length=15)
		user_doc.api_key = api_key
		user_doc.api_secret = api_secret
		user_doc.save(ignore_permissions=True)

	return api_key, api_secret


def _get_personnel(user: str) -> dict | None:
	name = frappe.db.get_value("Personnel", {"user_id": user}, "name")
	if not name:
		return None
	return frappe.get_doc("Personnel", name).as_dict()
