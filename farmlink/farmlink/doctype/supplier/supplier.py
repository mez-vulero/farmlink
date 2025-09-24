# Copyright (c) 2025, vulerotech and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import re

def _join_name_parts(*parts: str) -> str | None:
    """Join non-empty parts with single spaces, return None if all empty."""
    cleaned = []
    for p in parts:
        if not p:
            continue
        # normalize internal whitespace for each part
        p = re.sub(r"\s+", " ", p).strip()
        if p:
            cleaned.append(p)
    full = " ".join(cleaned).strip()
    return full or None

class Supplier(Document):
    def validate(self):
        # Called on save (insert/update). You can also use before_save().
        self.set_full_name()

    # If you prefer before_save over validate, define before_save and call set_full_name there.
    # def before_save(self):
    #     self.set_full_name()

    def set_full_name(self):
        # Use your actual fieldnames here if they differ
        first = getattr(self, "first_name", None)
        middle = getattr(self, "middle_name", None)
        last = getattr(self, "last_name", None)

        self.full_name = _join_name_parts(first, middle, last)
