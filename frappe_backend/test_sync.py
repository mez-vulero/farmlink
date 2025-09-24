#!/usr/bin/env python3
"""
FarmLink Sync Test Script
Test the Frappe backend sync endpoints
"""

import requests
import json
import time
from datetime import datetime

# Configuration
FRAPPE_BASE_URL = "https://farmlink.et"  # Update with your Frappe server URL
API_KEY = "your-api-key"  # Update with your API key
API_SECRET = "your-api-secret"  # Update with your API secret

def get_headers():
    """Get authentication headers"""
    return {
        'Authorization': f'token {API_KEY}:{API_SECRET}',
        'Content-Type': 'application/json'
    }

def test_connection():
    """Test basic connection to Frappe"""
    print("Testing connection...")
    
    try:
        response = requests.get(
            f"{FRAPPE_BASE_URL}/api/method/farmlink.sync.test_sync_connection",
            headers=get_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Connection successful: {data}")
            return True
        else:
            print(f"❌ Connection failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Connection error: {str(e)}")
        return False

def test_pull_changes():
    """Test pulling changes from Frappe"""
    print("\nTesting pull changes...")
    
    try:
        # Test with timestamp 0 to get all records
        payload = {"last_sync_timestamp": 0}
        
        response = requests.post(
            f"{FRAPPE_BASE_URL}/api/method/farmlink.sync.pull_changes",
            headers=get_headers(),
            data=json.dumps(payload),
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Pull changes successful")
            
            # Print summary of changes
            if 'message' in data and 'changes' in data['message']:
                changes = data['message']['changes']
                for table, table_changes in changes.items():
                    created = len(table_changes.get('created', []))
                    updated = len(table_changes.get('updated', []))
                    deleted = len(table_changes.get('deleted', []))
                    print(f"  {table}: {created} created, {updated} updated, {deleted} deleted")
            
            return True
        else:
            print(f"❌ Pull changes failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Pull changes error: {str(e)}")
        return False

def test_push_changes():
    """Test pushing sample changes to Frappe"""
    print("\nTesting push changes...")
    
    try:
        # Sample test data (this won't actually create records due to validation)
        sample_changes = {
            "changes": {
                "farmers": {
                    "created": [],
                    "updated": [],
                    "deleted": []
                }
            }
        }
        
        response = requests.post(
            f"{FRAPPE_BASE_URL}/api/method/farmlink.sync.push_changes",
            headers=get_headers(),
            data=json.dumps(sample_changes),
            timeout=30
        )
        
        if response.status_code == 200:
            print("✅ Push changes endpoint accessible")
            return True
        else:
            print(f"❌ Push changes failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Push changes error: {str(e)}")
        return False

def test_sync_status():
    """Test sync status endpoint"""
    print("\nTesting sync status...")
    
    try:
        response = requests.get(
            f"{FRAPPE_BASE_URL}/api/method/farmlink.sync.get_sync_status",
            headers=get_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Sync status successful")
            
            if 'message' in data and 'statistics' in data['message']:
                stats = data['message']['statistics']
                print("  Record counts:")
                for table, count in stats.items():
                    print(f"    {table}: {count}")
            
            return True
        else:
            print(f"❌ Sync status failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Sync status error: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("FarmLink Sync Test Suite")
    print("=" * 40)
    
    # Check configuration
    if API_KEY == "your-api-key" or API_SECRET == "your-api-secret":
        print("❌ Please update API_KEY and API_SECRET in the script")
        return
    
    # Run tests
    tests = [
        test_connection,
        test_sync_status,
        test_pull_changes,
        test_push_changes
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        time.sleep(1)  # Small delay between tests
    
    print("\n" + "=" * 40)
    print(f"Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All tests passed! Sync backend is ready.")
    else:
        print("⚠️  Some tests failed. Check configuration and Frappe setup.")

if __name__ == "__main__":
    main()
