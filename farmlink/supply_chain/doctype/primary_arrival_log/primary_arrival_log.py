# Copyright (c) 2025, vulerotech and contributors
# For license information, please see license.txt

# primary_arrival_log.py
import frappe
from frappe.model.document import Document
from farmlink.utils.csl import post_csl
from frappe.utils import flt

def on_submit(self):
    # + Cherry into on-hand (Primary Arrival bucket) at this washing station
    post_csl(
        station=self.center,                       # field exists on doc
        status="Primary Arrival",                  # CSL status option
        form="Cherry",                             # form
        qty=flt(self.collected_weight),            # field exists on doc
        ref_dt=self.doctype, ref_dn=self.name,
        remarks="Primary arrival of cherry"
    )

class PrimaryArrivalLog(Document):
	pass
