"""
FarmLink Sync Backend for Frappe
Handles WatermelonDB synchronization with Frappe backend
"""

import frappe
from frappe import _
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

# Doctype mappings between WatermelonDB and Frappe
DOCTYPE_MAPPINGS = {
    'farmers': 'Farmer',
    'payments': 'Payment', 
    'purchases': 'Purchase',
    'territories': 'Territory',
    'washing_stations': 'Washing Station'
}

# Field mappings from Frappe to WatermelonDB (snake_case to camelCase)
FIELD_MAPPINGS = {
    'naming_series': 'namingSeries',
    'first_name': 'firstName',
    'middle_name': 'middleName',
    'last_name': 'lastName',
    'phone_number': 'phoneNumber',
    'secondary_phone': 'secondaryPhone',
    'number_of_family': 'numberOfFamily',
    'no_family_members_attend_school': 'noFamilyMembersAttendSchool',
    'preferred_payment_method': 'preferredPaymentMethod',
    'bank_name': 'bankName',
    'bank_account_number': 'bankAccountNumber',
    'telebirr_phone_number': 'telebirrPhoneNumber',
    'total_farmland_ownership_hectares': 'totalFarmlandOwnershipHectares',
    'number_of_coffee_fields': 'numberOfCoffeeFields',
    'number_of_shade_trees': 'numberOfShadeTrees',
    'coffee_collection_center': 'coffeeCollectionCenter',
    'land_size_for_coffee_hectares': 'landSizeForCoffeeHectares',
    'coffee_trees_on_all_plots': 'coffeeTreesOnAllPlots',
    'number_of_temporary_workers': 'numberOfTemporaryWorkers',
    'frequent_field_agent_buyer': 'frequentFieldAgentBuyer',
    'farmers_photo': 'farmersPhoto',
    'bank_book': 'bankBook',
    'land_ownership_certificate': 'landOwnershipCertificate',
    'harvest_data': 'harvestData',
    'fertilizer_compost_usage': 'fertilizerCompostUsage',
    'custom_sync_status': 'customSyncStatus',
    'purchase_invoice': 'purchaseInvoice',
    'purchase_amount': 'purchaseAmount',
    'outstanding_amount': 'outstandingAmount',
    'payment_amount': 'paymentAmount',
    'mode_of_payment': 'modeOfPayment',
    'transaction_number': 'transactionNumber',
    'is_fully_paid': 'isFullyPaid',
    'collection_center': 'collectionCenter',
    'weight_in_kg': 'weightInKg',
    'price_rate_of_the_day': 'priceRateOfTheDay',
    'total_price': 'totalPrice',
    'coffee_grade': 'coffeeGrade',
    'purchase_date': 'purchaseDate',
    'territory_name': 'territoryName',
    'parent_territory': 'parentTerritory',
    'territory_manager': 'territoryManager',
    'station_name': 'stationName',
    'capacity_per_day': 'capacityPerDay',
    'contact_number': 'contactNumber',
}

def convert_frappe_to_watermelon(doc_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Frappe document fields to WatermelonDB format"""
    converted = {}
    
    for frappe_field, value in doc_dict.items():
        # Convert field name using mapping or keep as is
        watermelon_field = FIELD_MAPPINGS.get(frappe_field, frappe_field)
        
        # Handle datetime conversion
        if isinstance(value, datetime):
            converted[watermelon_field] = int(value.timestamp() * 1000)  # Convert to milliseconds
        elif value is not None:
            converted[watermelon_field] = value
    
    return converted

def convert_watermelon_to_frappe(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert WatermelonDB fields to Frappe format"""
    converted = {}
    
    # Reverse field mapping
    reverse_mappings = {v: k for k, v in FIELD_MAPPINGS.items()}
    
    for watermelon_field, value in data.items():
        # Convert field name using reverse mapping or keep as is
        frappe_field = reverse_mappings.get(watermelon_field, watermelon_field)
        
        # Handle timestamp conversion
        if watermelon_field.endswith('At') and isinstance(value, (int, float)):
            converted[frappe_field] = datetime.fromtimestamp(value / 1000)  # Convert from milliseconds
        elif value is not None:
            converted[frappe_field] = value
    
    return converted

@frappe.whitelist()
def pull_changes():
    """
    Pull changes from Frappe to WatermelonDB
    Expected to be called via POST with last_sync_timestamp
    """
    try:
        # Get request data
        data = json.loads(frappe.request.data) if frappe.request.data else {}
        last_sync_timestamp = data.get('last_sync_timestamp', 0)
        
        # Convert timestamp to datetime
        if last_sync_timestamp:
            last_sync_date = datetime.fromtimestamp(last_sync_timestamp / 1000)
        else:
            last_sync_date = datetime.min
        
        changes = {
            'farmers': {'created': [], 'updated': [], 'deleted': []},
            'payments': {'created': [], 'updated': [], 'deleted': []},
            'purchases': {'created': [], 'updated': [], 'deleted': []},
            'territories': {'created': [], 'updated': [], 'deleted': []},
            'washing_stations': {'created': [], 'updated': [], 'deleted': []}
        }
        
        # Pull changes for each doctype
        for watermelon_table, frappe_doctype in DOCTYPE_MAPPINGS.items():
            
            # Get created records (after last sync)
            created_docs = frappe.get_all(
                frappe_doctype,
                filters={'creation': ['>', last_sync_date]},
                fields=['*']
            )
            
            for doc_data in created_docs:
                # Get full document
                full_doc = frappe.get_doc(frappe_doctype, doc_data.name)
                converted_doc = convert_frappe_to_watermelon(full_doc.as_dict())
                converted_doc['id'] = doc_data.name  # Use Frappe name as ID
                changes[watermelon_table]['created'].append(converted_doc)
            
            # Get updated records (modified after creation and after last sync)
            updated_docs = frappe.get_all(
                frappe_doctype,
                filters={
                    'modified': ['>', last_sync_date],
                    'creation': ['<=', last_sync_date]  # Only records that existed before
                },
                fields=['*']
            )
            
            for doc_data in updated_docs:
                # Get full document
                full_doc = frappe.get_doc(frappe_doctype, doc_data.name)
                converted_doc = convert_frappe_to_watermelon(full_doc.as_dict())
                converted_doc['id'] = doc_data.name  # Use Frappe name as ID
                changes[watermelon_table]['updated'].append(converted_doc)
            
            # Note: Frappe doesn't have soft deletes by default, so we skip deleted records
            # You might want to implement a custom deletion tracking mechanism
        
        # Current timestamp for next sync
        current_timestamp = int(datetime.now().timestamp() * 1000)
        
        return {
            'changes': changes,
            'timestamp': current_timestamp
        }
        
    except Exception as e:
        frappe.log_error(f"Sync pull error: {str(e)}", "FarmLink Sync")
        frappe.throw(_("Failed to pull changes: {0}").format(str(e)))

@frappe.whitelist()
def push_changes():
    """
    Push changes from WatermelonDB to Frappe
    Expected to be called via POST with changes data
    """
    try:
        # Get request data
        data = json.loads(frappe.request.data) if frappe.request.data else {}
        changes = data.get('changes', {})
        
        # Process changes for each doctype
        for watermelon_table, table_changes in changes.items():
            frappe_doctype = DOCTYPE_MAPPINGS.get(watermelon_table)
            
            if not frappe_doctype:
                continue
            
            # Process created records
            for created_record in table_changes.get('created', []):
                try:
                    # Convert WatermelonDB data to Frappe format
                    frappe_data = convert_watermelon_to_frappe(created_record)
                    
                    # Create new document
                    doc = frappe.get_doc({
                        'doctype': frappe_doctype,
                        **frappe_data
                    })
                    
                    # Set the name if provided (for consistent IDs)
                    if 'id' in created_record:
                        doc.name = created_record['id']
                    
                    doc.insert(ignore_permissions=True)
                    frappe.db.commit()
                    
                except Exception as e:
                    frappe.log_error(f"Error creating {frappe_doctype}: {str(e)}", "FarmLink Sync")
                    continue
            
            # Process updated records
            for updated_record in table_changes.get('updated', []):
                try:
                    record_id = updated_record.get('id')
                    if not record_id:
                        continue
                    
                    # Check if document exists
                    if not frappe.db.exists(frappe_doctype, record_id):
                        frappe.log_error(f"Document {frappe_doctype} {record_id} not found for update", "FarmLink Sync")
                        continue
                    
                    # Get existing document
                    doc = frappe.get_doc(frappe_doctype, record_id)
                    
                    # Convert and update fields
                    frappe_data = convert_watermelon_to_frappe(updated_record)
                    
                    for field, value in frappe_data.items():
                        if field != 'name' and hasattr(doc, field):
                            setattr(doc, field, value)
                    
                    doc.save(ignore_permissions=True)
                    frappe.db.commit()
                    
                except Exception as e:
                    frappe.log_error(f"Error updating {frappe_doctype} {record_id}: {str(e)}", "FarmLink Sync")
                    continue
            
            # Process deleted records
            for deleted_record in table_changes.get('deleted', []):
                try:
                    record_id = deleted_record.get('id')
                    if not record_id:
                        continue
                    
                    # Check if document exists
                    if frappe.db.exists(frappe_doctype, record_id):
                        frappe.delete_doc(frappe_doctype, record_id, ignore_permissions=True)
                        frappe.db.commit()
                    
                except Exception as e:
                    frappe.log_error(f"Error deleting {frappe_doctype} {record_id}: {str(e)}", "FarmLink Sync")
                    continue
        
        return {'status': 'success', 'message': 'Changes pushed successfully'}
        
    except Exception as e:
        frappe.log_error(f"Sync push error: {str(e)}", "FarmLink Sync")
        frappe.throw(_("Failed to push changes: {0}").format(str(e)))

@frappe.whitelist()
def get_sync_status():
    """Get sync status and statistics"""
    try:
        stats = {}
        
        for watermelon_table, frappe_doctype in DOCTYPE_MAPPINGS.items():
            count = frappe.db.count(frappe_doctype)
            stats[watermelon_table] = count
        
        return {
            'status': 'ready',
            'statistics': stats,
            'server_time': int(datetime.now().timestamp() * 1000)
        }
        
    except Exception as e:
        frappe.log_error(f"Sync status error: {str(e)}", "FarmLink Sync")
        return {'status': 'error', 'message': str(e)}
