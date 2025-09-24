"""
FarmLink Sync Backend for Frappe
Handles WatermelonDB synchronization with Frappe backend
"""

import time
import json
import frappe
from frappe import _
from datetime import datetime
from typing import Dict, List, Any, Optional

# Doctype mappings between WatermelonDB and Frappe
DOCTYPE_MAPPINGS = {
    'farmers': 'Farmers',
    'payments': 'Payment', 
    'purchases': 'Purchases',
    'territories': 'Territory',
    'washing_stations': 'Washing Station',
    'dispatches': 'Dispatches',
    'arrival_logs': 'Arrival Log',
    'supplier_dispatches': 'Supplier Dispatch',
    'supplier_purchases': 'Supplier Purchase',
}

# Processing order for dependencies (independent first)
PROCESSING_ORDER = ['territories', 'washing_stations', 'farmers', 'purchases', 'payments', 'dispatches', 'supplier_dispatches', 'supplier_purchases', 'arrival_logs']

# Link field mappings for dependency resolution
LINK_FIELD_MAPPINGS = {
    'farmers': {
        'territory': 'territories',
        'specific_name_of_coffee_collection_center': 'washing_stations'
    },
    'purchases': {
        'farmer': 'farmers',
        'collection_center': 'washing_stations'
    },
    'payments': {
        'farmer': 'farmers',
        'purchase_invoice': 'purchases'
    },
    'territories': {
        'parent_territory': 'territories'  # Self-reference
    },
    'washing_stations': {
        'territory': 'territories'
    },
    'dispatches': {
        'dispatched_from': 'washing_stations',
        'territory': 'territories'
    },
    'arrival_logs': {
        'dispatch_log': 'dispatches',
        'arrival_center': 'washing_stations'
    },
    'supplier_dispatches': {
        # No linked fields - independent
    },
    'supplier_purchases': {
        # No linked fields - independent
    }
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
    'washing_station': 'washingStation',
    'dispatch_date': 'dispatchDate',
    'total_weight': 'totalWeight',
    'number_of_bags': 'numberOfBags',
    'destination': 'destination',
    'driver_name': 'driverName',
    'vehicle_plate_number': 'vehiclePlateNumber',
    'dispatch_status': 'dispatchStatus',
    'dispatched_by': 'dispatchedBy',
    'dispatched_from': 'dispatchedFrom',
    'dispatched_on': 'dispatchedOn',
    'plate_number': 'plateNumber',
    'drivers_name': 'driversName',
    'moisture_': 'moisture',
    'dispatch_log': 'dispatchLog',
    'delivery_status': 'deliveryStatus',
    'quantity_missing_in_bags': 'quantityMissingInBags',
    'quantity_missing_in_weightkg': 'quantityMissingInWeightkg',
    'collected_by': 'collectedBy',
    'arrival_time': 'arrivalTime',
    'arrival_center': 'arrivalCenter',
    'coffee_type': 'coffeeType',
    'unit_price': 'unitPrice',
    'purchased_by': 'purchasedBy',
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

def resolve_link_references(record_data: Dict[str, Any], table_name: str, id_mappings: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
    """
    Resolve WatermelonDB IDs to Frappe IDs for linked fields
    
    Args:
        record_data: The record data with potential WatermelonDB IDs
        table_name: The current table being processed
        id_mappings: Dictionary mapping WatermelonDB IDs to Frappe IDs for each table
    
    Returns:
        Record data with resolved Frappe IDs
    """
    resolved_data = record_data.copy()
    
    # Get link field mappings for this table
    link_fields = LINK_FIELD_MAPPINGS.get(table_name, {})
    
    for field_name, target_table in link_fields.items():
        if field_name in resolved_data and resolved_data[field_name]:
            watermelon_id = resolved_data[field_name]
            
            # Check if we have a mapping for this WatermelonDB ID
            if target_table in id_mappings and watermelon_id in id_mappings[target_table]:
                frappe_id = id_mappings[target_table][watermelon_id]
                resolved_data[field_name] = frappe_id
                frappe.logger().info(f"🔗 Resolved {field_name}: {watermelon_id} → {frappe_id}")
            else:
                # Check if it's already a Frappe ID (exists in the target doctype)
                target_doctype = DOCTYPE_MAPPINGS.get(target_table)
                if target_doctype and frappe.db.exists(target_doctype, watermelon_id):
                    frappe.logger().info(f"✅ {field_name} already has valid Frappe ID: {watermelon_id}")
                else:
                    frappe.logger().warning(f"⚠️ Could not resolve {field_name}: {watermelon_id} in {target_table}")
    
    return resolved_data

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
            'washing_stations': {'created': [], 'updated': [], 'deleted': []},
            'dispatches': {'created': [], 'updated': [], 'deleted': []},
            'arrival_logs': {'created': [], 'updated': [], 'deleted': []},
            'supplier_dispatches': {'created': [], 'updated': [], 'deleted': []},
            'supplier_purchases': {'created': [], 'updated': [], 'deleted': []},
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
                converted_doc = full_doc.as_dict()
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
                converted_doc = full_doc.as_dict()
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
    Push changes from WatermelonDB to Frappe with dependency resolution
    Expected to be called via POST with changes data
    Returns detailed information about processed records
    """
    try:
        # Get request data
        data = json.loads(frappe.request.data) if frappe.request.data else {}
        changes = data.get('changes', {})

        # Track processed records for detailed response
        processed = {}
        
        # Track ID mappings: WatermelonDB ID -> Frappe ID for each table
        id_mappings = {table: {} for table in PROCESSING_ORDER}

        frappe.logger().info("🚀 Starting push sync with dependency resolution")

        # Process changes in dependency order
        for watermelon_table in PROCESSING_ORDER:
            if watermelon_table not in changes:
                continue
                
            table_changes = changes[watermelon_table]
            frappe_doctype = DOCTYPE_MAPPINGS.get(watermelon_table)

            if not frappe_doctype:
                continue

            frappe.logger().info(f"📋 Processing {watermelon_table} ({frappe_doctype})")

            # Initialize tracking for this table
            processed[watermelon_table] = {
                'created': [],
                'updated': [],
                'deleted': [],
                'failed': []
            }

            # Process created records first
            for created_record in table_changes.get('created', []):
                try:
                    # Skip if already has frappe_id (shouldn't be in created)
                    if created_record.get('frappe_id'):
                        frappe.logger().info(f"⏭️ Skipping record with existing frappe_id: {created_record.get('frappe_id')}")
                        continue

                    # Convert WatermelonDB data to Frappe format
                    frappe_data = convert_watermelon_to_frappe(created_record)

                    # Resolve linked field references using ID mappings
                    frappe_data = resolve_link_references(frappe_data, watermelon_table, id_mappings)

                    # Remove sync status field as it's not needed in Frappe
                    frappe_data.pop('custom_sync_status', None)
                    frappe_data.pop('frappe_id', None)

                    frappe.logger().info(f"📝 Creating {frappe_doctype} with resolved data")

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

                    # Store ID mapping for future references
                    watermelon_id = created_record.get('id') or created_record.get('name')
                    if watermelon_id:
                        id_mappings[watermelon_table][watermelon_id] = doc.name
                        frappe.logger().info(f"✅ Created {frappe_doctype}: {watermelon_id} → {doc.name}")

                    # Track successful creation
                    processed[watermelon_table]['created'].append({
                        "watermelon_id": watermelon_id,
                        "frappe_name": doc.name
                    })

                except Exception as e:
                    frappe.log_error(f"Error creating {frappe_doctype}: {str(e)}", "FarmLink Sync")
                    processed[watermelon_table]['failed'].append({
                        'id': created_record.get('id', 'unknown'),
                        'operation': 'create',
                        'error': str(e)
                    })
                    frappe.logger().error(f"❌ Failed to create {frappe_doctype}: {str(e)}")
                    continue

            # Process updated records (after all creations to ensure dependencies exist)
            for updated_record in table_changes.get('updated', []):
                try:
                    record_id = updated_record.get('frappe_id') or updated_record.get('name')
                    if not record_id:
                        continue

                    # Check if document exists
                    if not frappe.db.exists(frappe_doctype, record_id):
                        frappe.log_error(f"Document {frappe_doctype} {record_id} not found for update", "FarmLink Sync")
                        processed[watermelon_table]['failed'].append({
                            'id': record_id,
                            'operation': 'update',
                            'error': 'Document not found'
                        })
                        continue

                    # Get existing document
                    doc = frappe.get_doc(frappe_doctype, record_id)

                    # Convert and resolve linked fields
                    frappe_data = convert_watermelon_to_frappe(updated_record)
                    frappe_data = resolve_link_references(frappe_data, watermelon_table, id_mappings)

                    # Remove sync status and other metadata fields
                    frappe_data.pop('custom_sync_status', None)
                    frappe_data.pop('creation', None)
                    frappe_data.pop('modified', None)
                    frappe_data.pop('frappe_id', None)

                    for field, value in frappe_data.items():
                        if field not in ['name', 'doctype'] and hasattr(doc, field):
                            setattr(doc, field, value)

                    doc.save(ignore_permissions=True)
                    frappe.db.commit()

                    frappe.logger().info(f"✅ Updated {frappe_doctype}: {record_id}")
                    # Track successful update
                    processed[watermelon_table]['updated'].append(record_id)

                except Exception as e:
                    frappe.log_error(f"Error updating {frappe_doctype} {record_id}: {str(e)}", "FarmLink Sync")
                    processed[watermelon_table]['failed'].append({
                        'id': updated_record.get('name') or updated_record.get('id', 'unknown'),
                        'operation': 'update',
                        'error': str(e)
                    })
                    continue

            # Process deleted records
            for deleted_record in table_changes.get('deleted', []):
                try:
                    #record_id = deleted_record.get('id')
                    record_id = deleted_record;
                    if not record_id:
                        continue

                    # Check if document exists
                    if frappe.db.exists(frappe_doctype, record_id):
                        frappe.delete_doc(frappe_doctype, record_id, ignore_permissions=True)
                        frappe.db.commit()
                        frappe.logger().info(f"🗑️ Deleted {frappe_doctype}: {record_id}")

                        # Track successful deletion
                        #processed[watermelon_table]['deleted'].append(record_id)

                except Exception as e:
                    frappe.log_error(f"Error deleting {frappe_doctype} {record_id}: {str(e)}", "FarmLink Sync")
                    processed[watermelon_table]['failed'].append({
                        'id': deleted_record.get('id', 'unknown'),
                        'operation': 'delete',
                        'error': str(e)
                    })
                    continue

        frappe.logger().info("🎉 Push sync completed with dependency resolution")

        # Return detailed response with processing information
        return {
            'status': 'success',
            'message': 'Changes pushed successfully with dependency resolution',
            'processed': processed,
            'id_mappings': id_mappings,  # Include mappings for client reference
            'timestamp': int(time.time() * 1000)  # Current server timestamp in milliseconds
        }

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
