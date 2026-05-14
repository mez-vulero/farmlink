# Copyright (c) 2025, vulerotech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PrimaryArrivalLog(Document):
	def validate(self):
		self._normalize_collector_fields()

	def _normalize_collector_fields(self):
		"""Enforce mutual exclusion between the Dynamic Link and the free-text name.

		The mobile UI lets field officers either pick a Personnel/Supplier from
		the list or type a name freehand when the collector isn't yet in the
		master tables. We keep the link column clean (so reports that JOIN on
		Personnel/Supplier stay correct) by clearing whichever field isn't in
		use for this particular row.
		"""
		if not self.collected_from:
			# Nothing chosen yet — leave the fields alone so the form can be
			# saved mid-edit. Save() will be blocked elsewhere by required-by-UI.
			return

		if self.is_external_collector:
			if not (self.external_collector_name or "").strip():
				frappe.throw(
					"External Collector Name is required when 'Type Name Manually' is checked."
				)
			# Defensive: clear the link so reports that JOIN through it don't
			# see a phantom Personnel/Supplier reference for an externally-named row.
			self.collected_from_name = None
		else:
			if not self.collected_from_name:
				frappe.throw(
					"Collected From Name is required. Either pick from the list or"
					" check 'Type Name Manually' and type the name."
				)
			# Defensive: keep the free-text column empty for picked entries.
			self.external_collector_name = None

	@property
	def display_collector(self) -> str:
		"""Single readable name for templates/reports.

		Returns the typed name when external, the linked record name otherwise.
		"""
		if self.is_external_collector:
			return (self.external_collector_name or "").strip()
		return self.collected_from_name or ""
