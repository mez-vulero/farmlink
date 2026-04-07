import frappe
from frappe.model.document import Document
from frappe.utils import flt


class CuppingOrder(Document):
    def validate(self):
        self._compute_total_score()

    def _compute_total_score(self):
        score_fields = [
            "fragrance_aroma", "flavor", "aftertaste", "acidity",
            "body", "balance", "uniformity", "overall",
        ]
        total = sum(flt(self.get(f)) for f in score_fields)
        self.total_score = total

        if total >= 85:
            self.cup_classification = "Specialty"
        elif total >= 80:
            self.cup_classification = "Premium"
        elif total >= 75:
            self.cup_classification = "Commercial High"
        elif total >= 70:
            self.cup_classification = "Commercial"
        else:
            self.cup_classification = "Below Commercial"
