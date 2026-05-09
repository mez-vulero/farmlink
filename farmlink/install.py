"""
Install / migrate hooks for FarmLink.

Seeds the four custom Frappe Roles that mirror the Personnel.designation values
the mobile app already uses for its client-side role matrix
(services/role-permissions.service.ts):

  - FarmLink Area Manager
  - FarmLink Purchase and Finance
  - FarmLink Arrival and Processing
  - FarmLink Warehouse

Roles are non-desk by default — they exist purely so permission_query_conditions
and DocPerm rules can reference them. Desk users keep their existing roles
(System Manager, Farmlink Manager, Collector, etc.) untouched.

Idempotent: safe to call from after_install AND after_migrate.
"""

import frappe


FARMLINK_ROLES = (
	"FarmLink Area Manager",
	"FarmLink Purchase and Finance",
	"FarmLink Arrival and Processing",
	"FarmLink Warehouse",
)


def after_install():
	_seed_roles()


def after_migrate():
	_seed_roles()


def _seed_roles():
	for role_name in FARMLINK_ROLES:
		if frappe.db.exists("Role", role_name):
			continue
		frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": role_name,
				"desk_access": 0,
				"is_custom": 1,
			}
		).insert(ignore_permissions=True)
