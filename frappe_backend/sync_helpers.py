"""
FarmLink Sync Helper Functions
Additional utilities for WatermelonDB sync with Frappe
"""

import frappe
from datetime import datetime
from typing import Dict, List, Any

def on_farmer_change(doc, method):
    """Called when Farmer document changes"""
    log_sync_event('Farmer', doc.name, method)

def on_payment_change(doc, method):
    """Called when Payment document changes"""
    log_sync_event('Payment', doc.name, method)

def on_purchase_change(doc, method):
    """Called when Purchase document changes"""
    log_sync_event('Purchase', doc.name, method)

def on_territory_change(doc, method):
    """Called when Territory document changes"""
    log_sync_event('Territory', doc.name, method)

def on_washing_station_change(doc, method):
    """Called when Washing Station document changes"""
    log_sync_event('Washing Station', doc.name, method)

def log_sync_event(doctype: str, docname: str, method: str):
    """Log sync events for debugging"""
    frappe.logger().info(f"FarmLink Sync Event: {doctype} {docname} - {method}")

def daily_sync_cleanup():
    """Daily cleanup of sync logs and temporary data"""
    try:
        # Clean up old sync logs (older than 30 days)
        frappe.db.sql("""
            DELETE FROM `tabError Log` 
            WHERE creation < DATE_SUB(NOW(), INTERVAL 30 DAY)
            AND error LIKE '%FarmLink Sync%'
        """)
        
        frappe.logger().info("FarmLink: Daily sync cleanup completed")
        
    except Exception as e:
        frappe.log_error(f"Daily sync cleanup error: {str(e)}", "FarmLink Sync")

@frappe.whitelist()
def test_sync_connection():
    """Test endpoint to verify sync connectivity"""
    return {
        'status': 'success',
        'message': 'FarmLink sync connection successful',
        'server_time': datetime.now().isoformat(),
        'frappe_version': frappe.__version__
    }

@frappe.whitelist()
def get_doctype_schema(doctype_name: str):
    """Get schema information for a doctype (useful for debugging field mappings)"""
    try:
        meta = frappe.get_meta(doctype_name)
        fields = []
        
        for field in meta.fields:
            fields.append({
                'fieldname': field.fieldname,
                'fieldtype': field.fieldtype,
                'label': field.label,
                'reqd': field.reqd,
                'options': field.options
            })
        
        return {
            'doctype': doctype_name,
            'fields': fields
        }
        
    except Exception as e:
        frappe.throw(f"Error getting schema for {doctype_name}: {str(e)}")

def validate_sync_data(doctype: str, data: Dict[str, Any]) -> List[str]:
    """Validate sync data against Frappe doctype schema"""
    errors = []
    
    try:
        meta = frappe.get_meta(doctype)
        
        # Check required fields
        for field in meta.fields:
            if field.reqd and field.fieldname not in data:
                errors.append(f"Required field '{field.fieldname}' is missing")
        
        # Check field types (basic validation)
        for fieldname, value in data.items():
            if hasattr(meta, 'get_field'):
                field = meta.get_field(fieldname)
                if field and field.fieldtype == 'Int' and not isinstance(value, int):
                    errors.append(f"Field '{fieldname}' should be an integer")
                elif field and field.fieldtype == 'Float' and not isinstance(value, (int, float)):
                    errors.append(f"Field '{fieldname}' should be a number")
        
    except Exception as e:
        errors.append(f"Validation error: {str(e)}")
    
    return errors
