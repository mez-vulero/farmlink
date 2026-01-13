import frappe

FARMLINK_ROLES = {
	"Farmlink Manager",
	"Collector",
	"Finance Officer",
	"Arrival Clerk",
	"Dispatch Clerk",
}


def boot_session(bootinfo):
	roles = set(frappe.get_roles())
	has_farmlink_role = bool(roles & FARMLINK_ROLES)
	is_sys_manager = "System Manager" in roles

	if has_farmlink_role:
		_prioritize_farmlink_app(bootinfo)

		# For operational users keep the sidebar focused on FarmLink and core frappe.
		if not is_sys_manager:
			_limit_apps_for_farmlink_users(bootinfo)
	else:
		_prioritize_farmlink_app(bootinfo, keep_others=True)


def _prioritize_farmlink_app(bootinfo, keep_others: bool = False):
	"""Move FarmLink ahead of other apps in the app switcher."""
	apps = bootinfo.get("app_data") or []
	apps.sort(key=lambda app: 0 if app.get("app_name") == "farmlink" else 1)
	if keep_others:
		bootinfo["app_data"] = apps
	elif apps:
		bootinfo["app_data"] = [app for app in apps if app.get("app_name") == "farmlink"] + [
			app for app in apps if app.get("app_name") != "farmlink"
		]


def _limit_apps_for_farmlink_users(bootinfo):
	"""Trim sidebar noise when the user only needs FarmLink."""
	allowed_apps = {"farmlink", "frappe"}

	apps = bootinfo.get("app_data") or []
	bootinfo["app_data"] = [app for app in apps if app.get("app_name") in allowed_apps] or apps

	pages = bootinfo.get("sidebar_pages", {}).get("pages", [])
	bootinfo["sidebar_pages"]["pages"] = [
		page for page in pages if (page.get("app") in allowed_apps or not page.get("public"))
	]
