# Copyright (c) 2026, vulerotech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ReceiptString(Document):
	def validate(self):
		# Trim whitespace on the printed value — leading/trailing spaces sneak in
		# easily from copy-paste and would print as ragged labels on the thermal.
		if self.value:
			self.value = self.value.rstrip()

		# Uniqueness on (target_doctype, string_key). The autoname format
		# already enforces this at the DB level, but a friendly error beats a
		# 1062 Duplicate entry.
		if not self.target_doctype or not self.string_key:
			return
		expected_name = f"{self.target_doctype}-{self.string_key}"
		if self.name and self.name != expected_name:
			# Renaming-style edit; let Frappe's rename machinery handle it.
			return
		existing = frappe.db.exists(
			"Receipt String",
			{
				"target_doctype": self.target_doctype,
				"string_key": self.string_key,
				"name": ["!=", self.name or ""],
			},
		)
		if existing:
			frappe.throw(
				f"A Receipt String for {self.target_doctype} / {self.string_key} already exists.",
				frappe.DuplicateEntryError,
			)
