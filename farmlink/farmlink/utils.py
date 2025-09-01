# Copyright (c) 2025, vulerotech and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def get_purchase_payment_summary(purchase_name):
	"""
	Get payment summary for a purchase
	
	Args:
		purchase_name (str): Name of the purchase document
		
	Returns:
		dict: Payment summary with total_paid, outstanding_amount, and payment_status
	"""
	if not purchase_name:
		return {}
	
	# Get purchase details
	purchase = frappe.get_doc("Purchase", purchase_name)
	if not purchase:
		return {}
	
	# Calculate total paid amount
	total_paid = frappe.db.sql("""
		SELECT COALESCE(SUM(payment_amount), 0)
		FROM `tabPayment`
		WHERE purchase_invoice = %s AND docstatus = 1
	""", purchase_name)
	
	total_paid = total_paid[0][0] if total_paid else 0.0
	outstanding = purchase.total_amount - total_paid
	
	# Determine payment status
	if outstanding <= 0:
		payment_status = "Paid"
	elif total_paid > 0:
		payment_status = "Partially Paid"
	else:
		payment_status = "Unpaid"
	
	return {
		"total_paid": total_paid,
		"outstanding_amount": outstanding,
		"payment_status": payment_status
	}

def update_purchase_payment_status(purchase_name):
	"""
	Update payment status of a purchase based on payments
	
	Args:
		purchase_name (str): Name of the purchase document
	"""
	if not purchase_name:
		return
	
	try:
		purchase = frappe.get_doc("Purchase", purchase_name)
		if purchase:
			purchase.update_payment_status()
			purchase.save()
	except Exception as e:
		frappe.log_error(f"Error updating purchase payment status: {str(e)}")

def validate_payment_amount(purchase_name, payment_amount):
	"""
	Validate if payment amount is valid for a purchase
	
	Args:
		purchase_name (str): Name of the purchase document
		payment_amount (float): Amount to be paid
		
	Returns:
		tuple: (is_valid, error_message)
	"""
	if not purchase_name or not payment_amount:
		return False, "Invalid purchase or payment amount"
	
	purchase = frappe.get_doc("Purchase", purchase_name)
	if not purchase:
		return False, "Purchase not found"
	
	if purchase.docstatus != 1:
		return False, "Payment can only be made against submitted purchases"
	
	if purchase.payment_status == "Paid":
		return False, "Purchase is already fully paid"
	
	if payment_amount <= 0:
		return False, "Payment amount must be greater than zero"
	
	if payment_amount > purchase.outstanding_amount:
		return False, f"Payment amount ({payment_amount}) cannot exceed outstanding amount ({purchase.outstanding_amount})"
	
	return True, ""

def get_daily_price_for_date(date, territory=None):
	"""
	Get daily price for coffee cherries on a specific date
	
	Args:
		date (str): Date in YYYY-MM-DD format
		territory (str): Territory name (optional)
		
	Returns:
		float: Daily price per kg
	"""
	# This is a placeholder function - you can implement your own logic
	# to fetch daily prices from a price list or external API
	
	# For now, return a default price
	default_price = 150.0  # ETB per kg
	
	# You can implement logic like:
	# - Fetch from a Price List DocType
	# - Call external API for market prices
	# - Use seasonal pricing rules
	
	return default_price

def refresh_all_purchase_payment_statuses():
	"""
	Refresh payment statuses for all submitted purchases
	This function can be called to fix existing data issues
	"""
	try:
		# Get all submitted purchases
		purchases = frappe.get_all("Purchase", 
			filters={"docstatus": 1},
			fields=["name"]
		)
		
		updated_count = 0
		error_count = 0
		
		for purchase in purchases:
			try:
				update_purchase_payment_status(purchase.name)
				updated_count += 1
			except Exception as e:
				error_count += 1
				frappe.log_error(f"Error updating purchase {purchase.name}: {str(e)}")
		
		# Commit all changes
		frappe.db.commit()
		
		return {
			"success": True,
			"updated": updated_count,
			"errors": error_count,
			"message": f"Updated {updated_count} purchases. {error_count} errors occurred."
		}
		
	except Exception as e:
		frappe.log_error(f"Error in refresh_all_purchase_payment_statuses: {str(e)}")
		return {
			"success": False,
			"error": str(e)
		}

def force_update_purchase_payment_status(purchase_name):
	"""
	Force update payment status for a specific purchase
	This bypasses normal validation and forces a recalculation
	
	Args:
		purchase_name (str): Name of the purchase document
		
	Returns:
		dict: Result of the update operation
	"""
	try:
		purchase = frappe.get_doc("Purchase", purchase_name)
		if not purchase:
			return {"success": False, "error": "Purchase not found"}
		
		# Calculate total paid amount directly
		total_paid = frappe.db.sql("""
			SELECT COALESCE(SUM(payment_amount), 0)
			FROM `tabPayment`
			WHERE purchase_invoice = %s AND docstatus = 1
		""", purchase_name)
		
		total_paid = total_paid[0][0] if total_paid else 0.0
		outstanding = purchase.total_amount - total_paid
		
		# Determine payment status
		if outstanding <= 0:
			payment_status = "Paid"
		elif total_paid > 0:
			payment_status = "Partially Paid"
		else:
			payment_status = "Unpaid"
		
		# Update the fields directly
		purchase.paid_amount = total_paid
		purchase.outstanding_amount = outstanding
		purchase.payment_status = payment_status
		
		# Save the document
		purchase.save()
		
		# Commit the transaction
		frappe.db.commit()
		
		return {
			"success": True,
			"paid_amount": total_paid,
			"outstanding_amount": outstanding,
			"payment_status": payment_status
		}
		
	except Exception as e:
		frappe.log_error(f"Error in force_update_purchase_payment_status: {str(e)}")
		return {"success": False, "error": str(e)} 