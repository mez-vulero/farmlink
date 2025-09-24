# FarmLink Frappe Backend Setup Guide

This guide explains how to set up the Frappe backend to work with the FarmLink WatermelonDB sync system.

## Prerequisites

- Frappe Framework installed and running
- FarmLink Frappe app created
- API access enabled on your Frappe site

## 1. Frappe App Structure

Create a new Frappe app or add to existing app:

```bash
# Create new app (if needed)
bench new-app farmlink

# Install app on site
bench --site your-site.com install-app farmlink
```

## 2. File Structure

Place the sync files in your Frappe app directory:

```
farmlink/
├── farmlink/
│   ├── __init__.py
│   ├── hooks.py                 # App configuration
│   ├── sync/
│   │   ├── __init__.py
│   │   ├── farmlink_sync.py     # Main sync functions
│   │   └── sync_helpers.py      # Helper functions
│   └── ...
```

## 3. API Endpoints

The following API endpoints will be available after setup:

### Pull Changes (GET/POST)
```
https://your-site.com/api/method/farmlink.sync.pull_changes
```

**Request Body:**
```json
{
  "last_sync_timestamp": 1693834567000
}
```

**Response:**
```json
{
  "changes": {
    "farmers": {
      "created": [...],
      "updated": [...], 
      "deleted": [...]
    },
    "payments": {...},
    "purchases": {...},
    "territories": {...},
    "washing_stations": {...}
  },
  "timestamp": 1693834567000
}
```

### Push Changes (POST)
```
https://your-site.com/api/method/farmlink.sync.push_changes
```

**Request Body:**
```json
{
  "changes": {
    "farmers": {
      "created": [...],
      "updated": [...],
      "deleted": [...]
    }
  }
}
```

### Sync Status (GET)
```
https://your-site.com/api/method/farmlink.sync.get_sync_status
```

### Test Connection (GET)
```
https://your-site.com/api/method/farmlink.sync.test_sync_connection
```

## 4. Authentication Setup

### Option A: API Key/Secret (Recommended)

1. Create API Key and Secret:
```bash
# In Frappe console
bench --site your-site.com console

# Create user for sync
user = frappe.get_doc({
    'doctype': 'User',
    'email': 'sync@farmlink.et',
    'first_name': 'Sync',
    'user_type': 'System User'
})
user.insert()

# Generate API key
api_key = frappe.generate_hash(length=15)
api_secret = frappe.generate_hash(length=15)

# Save API credentials
frappe.get_doc({
    'doctype': 'User',
    'name': 'sync@farmlink.et',
    'api_key': api_key,
    'api_secret': api_secret
}).save()

print(f"API Key: {api_key}")
print(f"API Secret: {api_secret}")
```

2. Update your React Native app config:
```typescript
// config/sync.config.ts
export const SYNC_CONFIG = {
  FRAPPE_BASE_URL: 'https://your-site.com',
  API_KEY: 'your-generated-api-key',
  API_SECRET: 'your-generated-api-secret',
  // ...
}
```

### Option B: Token Authentication

1. Create authentication token in Frappe
2. Use Bearer token in Authorization header

## 5. Doctype Configuration

Ensure your Frappe doctypes match the expected structure:

### Farmer Doctype Fields
- `naming_series` (Data)
- `first_name` (Data)
- `middle_name` (Data) 
- `last_name` (Data)
- `phone_number` (Data)
- `secondary_phone` (Data)
- `territory` (Link - Territory)
- `washing_station` (Link - Washing Station)
- ... (other fields as per your schema)

### Payment Doctype Fields
- `naming_series` (Data)
- `farmer` (Link - Farmer)
- `purchase_invoice` (Link - Purchase)
- `payment_amount` (Currency)
- `mode_of_payment` (Data)
- ... (other fields)

### Purchase Doctype Fields
- `naming_series` (Data)
- `farmer` (Link - Farmer)
- `territory` (Link - Territory)
- `washing_station` (Link - Washing Station)
- `weight_in_kg` (Float)
- `total_price` (Currency)
- ... (other fields)

## 6. Permissions Setup

Grant appropriate permissions to the sync user:

```python
# In Frappe console
from frappe.permissions import add_permission

# Grant permissions for sync user
doctypes = ['Farmer', 'Payment', 'Purchase', 'Territory', 'Washing Station']

for doctype in doctypes:
    add_permission(doctype, 'sync@farmlink.et', 0)  # Read
    add_permission(doctype, 'sync@farmlink.et', 1)  # Write
    add_permission(doctype, 'sync@farmlink.et', 2)  # Create
    add_permission(doctype, 'sync@farmlink.et', 3)  # Delete
```

## 7. Testing the Setup

1. Test connection:
```bash
curl -X GET "https://your-site.com/api/method/farmlink.sync.test_sync_connection" \
  -H "Authorization: token your-api-key:your-api-secret"
```

2. Test pull changes:
```bash
curl -X POST "https://your-site.com/api/method/farmlink.sync.pull_changes" \
  -H "Authorization: token your-api-key:your-api-secret" \
  -H "Content-Type: application/json" \
  -d '{"last_sync_timestamp": 0}'
```

## 8. Deployment Considerations

### Production Setup
- Enable HTTPS/SSL
- Configure proper CORS settings
- Set up rate limiting
- Monitor API usage
- Regular database backups

### Performance Optimization
- Index frequently queried fields (creation, modified)
- Consider pagination for large datasets
- Implement caching where appropriate
- Monitor sync performance

### Error Handling
- Check Frappe Error Logs for sync issues
- Monitor sync success/failure rates
- Set up alerts for sync failures

## 9. Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Verify API key/secret are correct
   - Check user permissions
   - Ensure user is active

2. **Field Mapping Errors**
   - Verify doctype field names match expectations
   - Check field types are compatible
   - Review field mappings in `farmlink_sync.py`

3. **Performance Issues**
   - Check database indexes
   - Monitor query performance
   - Consider implementing pagination

### Debug Mode
Enable debug logging in Frappe:
```python
# In site_config.json
{
  "developer_mode": 1,
  "log_level": "DEBUG"
}
```

## 10. Monitoring and Maintenance

- Regularly check sync logs
- Monitor API response times
- Update field mappings as schema evolves
- Backup sync configuration
- Test sync after Frappe updates

## Support

For issues with the sync implementation:
1. Check Frappe Error Logs
2. Review sync event logs
3. Test individual API endpoints
4. Verify data integrity after sync
