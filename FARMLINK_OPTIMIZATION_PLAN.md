# FarmLink App — Efficiency, Performance & Expansion Plan

> Generated: 2026-04-03 | Based on full codebase audit

## Context

FarmLink is a Frappe-based digital coffee management platform covering the full Ethiopian coffee supply chain: farmer registration, cherry purchasing, primary/secondary processing, stock tracking, payments, mobile sync, and sustainability assessments. It has **29 DocTypes across 3 modules**, a custom Coffee Stock Ledger (CSL), WatermelonDB offline sync, Bluetooth scale integration, Leaflet maps, and PWA scaffolding.

This plan identifies concrete improvements across security, performance, code quality, feature completeness, and expansion — based on a thorough audit of every file in the codebase.

---

## PHASE 1: Critical Security & Stability Fixes

### 1.1 Remove Guest Permissions from Sensitive DocTypes
- **Files:** `supply_chain/doctype/purchases/purchases.json:234`, `payment/payment.json:190`, `primary_arrival_log/primary_arrival_log.json:135`
- **Problem:** Unauthenticated users can read all purchase records, payment details, and arrival logs via `/api/resource/Purchases`
- **Fix:** Remove the `"role": "Guest"` permission block from all three JSON files
- **Priority:** CRITICAL | **Effort:** Low

### 1.2 Fix FIELD_MAPPINGS NameError in Sync Engine
- **File:** `farmlink/utils/farmlink_sync.py:72`
- **Problem:** `convert_watermelon_to_frappe()` references `FIELD_MAPPINGS` which is never defined — will crash at runtime
- **Fix:** Remove the dead function (it's unused by `push_changes()`) or import from `frappe_backend/farmlink_sync.py`
- **Priority:** CRITICAL | **Effort:** Low

### 1.3 Secure Sync Endpoints
- **File:** `farmlink/utils/farmlink_sync.py` — `push_changes()` at line 203
- **Problem:** Any logged-in user can push sync data that bypasses all Frappe permissions (`ignore_permissions=True` on every insert/save/delete)
- **Fix:** Add role checks (only Farmlink Manager, Collector), remove blanket `ignore_permissions=True`, add input sanitization
- **Priority:** CRITICAL | **Effort:** Medium

### 1.4 Remove `@frappe.whitelist()` from Internal CSL Functions
- **File:** `farmlink/utils/csl.py` — `center_balance()`, `record_transfer()`, `reverse_entries()`, `post_csl()`
- **Problem:** These internal inventory functions are callable via `/api/method/`, allowing any user to create arbitrary stock entries
- **Fix:** Remove `@frappe.whitelist()` — these should only be called from document hooks in `stock_ledger.py`
- **Priority:** CRITICAL | **Effort:** Low

### 1.5 Delete Dead Code & Duplicates
- **Files to remove:**
  - `frappe_backend/` — entire directory (duplicate older sync code)
  - `farmlink/utils/farmlink_sync.py.bak`
  - `farmlink/www/sw.js.bac`, `sw.js.back`
  - `farmlink/farmlink/utils.py` — stale file referencing nonexistent fields (`total_amount`, `paid_amount`, DocType "Purchase" instead of "Purchases")
  - `farmlink/agricultural_extension_services/` — empty module
  - `farmlink/utils/hooks.py` — orphan hooks file not referenced anywhere
- **Priority:** HIGH | **Effort:** Low

---

## PHASE 2: Data Integrity & Performance

### 2.1 Add Database Indexes to Coffee Stock Ledger
- **File:** `supply_chain/doctype/coffee_stock_ledger/coffee_stock_ledger.json`
- **Problem:** The CSL is the most query-heavy table — `_net_sum_query()` filters on `center`, `coffee_form`, `is_cancelled`, `entry_type` etc. with NO indexes
- **Fix:** Add `search_index: 1` to `center`, `is_cancelled`, `entry_type`, `reference_doctype`, `reference_name`, `entry_ref`. Create a composite index via migration patch on `(center, coffee_form, is_cancelled, entry_type)`
- **Priority:** CRITICAL | **Effort:** Low

### 2.2 Fix Field Type Mismatches in Secondary Arrival Log
- **File:** `supply_chain/doctype/secondary_arrival_log/secondary_arrival_log.json`
- **Problem:** `dispatched_weight_in_kg`, `quantity_missing_in_weightkg`, `dispatched_number_of_bags`, `moisture_on_dispatch` are all `Data` (string) type — should be `Float`/`Int`. Arithmetic in `stock_ledger.py:147-148` relies on `flt()` coercion
- **Fix:** Change field types in JSON schema + migration patch
- **Priority:** HIGH | **Effort:** Medium

### 2.3 Add Server-Side Validation to DocType Controllers
- **Problem:** 17 of 22 controllers are empty `pass` — no validation beyond JSON schema
- **Key controllers to add `validate()` to:**
  - **Purchases** (`purchases.py`): weight > 0, price > 0, total = weight x rate, farmer/supplier matches purchase_type
  - **Payment** (`payment.py`): amount > 0, amount <= outstanding, purchase exists and not fully paid
  - **Primary Arrival Log**: center set, weight > 0
  - **Primary Processing**: output weight <= input weight (mass conservation)
  - **Primary Dispatch**: source != destination center
- **Priority:** CRITICAL | **Effort:** High

### 2.4 Eliminate Per-Record `frappe.db.commit()` in Sync
- **File:** `farmlink/utils/farmlink_sync.py` lines 290, 361, 429, 454
- **Problem:** 4 separate `frappe.db.commit()` calls inside loops — syncing 100 records = 100 individual DB transactions
- **Fix:** Remove all per-record commits; let Frappe commit once at request end. For partial-failure handling, batch per-DocType
- **Priority:** CRITICAL | **Effort:** Low

### 2.5 Implement Redis Caching for CSL Balance Queries
- **File:** `farmlink/utils/csl.py`
- **Problem:** `frappe.cache` is never used anywhere. Every `center_balance()` call runs raw SQL. During processing saves, `_validate_out_qty` triggers redundant balance queries
- **Fix:** Cache balance results via `frappe.cache().hset()` with short TTL. Invalidate in `record_transfer()` and `reverse_entries()` — the only write paths
- **Priority:** HIGH | **Effort:** Medium

### 2.6 Fix pull_changes() N+1 Query Pattern
- **File:** `farmlink/utils/farmlink_sync.py:156-187`
- **Problem:** `pull_changes()` runs `frappe.get_all()` then loops `frappe.get_doc()` per record for 13 DocTypes — potentially thousands of individual queries
- **Fix:** Use `frappe.get_all(fields=['*'])` and batch-fetch child tables with `parent IN (...)` queries
- **Priority:** HIGH | **Effort:** Medium

---

## PHASE 3: Feature Completion

### 3.1 Implement the Daily Price System
- **File:** `farmlink/farmlink/utils.py:99` — `get_daily_price_for_date()` hardcodes `return 150.0`
- **Fix:** Create "Daily Coffee Price" DocType (date, territory, coffee_type, price_per_kg). Auto-populate `price_rate_of_the_day` on Purchase validate
- **Priority:** HIGH | **Effort:** Medium

### 3.2 Activate PWA / Service Worker
- **Problem:** `pwa-register.js` registers `/sw.js` but no active `sw.js` exists. Not included in `app_include_js`. Three backup files exist but none deployed
- **Fix:** Promote `sw.js.d` as the active service worker, add `pwa-register.js` to hooks.py includes, delete backups
- **Priority:** HIGH | **Effort:** Medium

### 3.3 Complete the Trades DocType
- **File:** `supply_chain/doctype/trades/trades.json` — only has `contract_number` and `customer` link
- **Fix:** Add `trade_date`, `coffee_form`, `coffee_grade`, `quantity_kg`, `price_per_kg`, `total_value`, `currency`, `shipping_status`. Connect to CSL with OUT entries. Add workflow: Draft -> Confirmed -> Shipped -> Delivered
- **Priority:** MEDIUM | **Effort:** High

### 3.4 Enable Scheduler Events
- **File:** `farmlink/hooks.py:215-231` — entirely commented out
- **Fix:** Activate: daily sync cleanup, stale purchase status refresh, weekly center summary reports
- **Priority:** MEDIUM | **Effort:** Medium

### 3.5 Develop Harvest Data & Fertilizer Usage
- **Problem:** Child table DocTypes with minimal fields. Year options hardcoded to 2015-2020 EC
- **Fix:** Make years dynamic, add `farm` link, `coffee_variety`, `fertilizer_type`, `application_date`. Add duplicate-year validation
- **Priority:** MEDIUM | **Effort:** Medium

### 3.6 Write Core Test Suite
- **Problem:** All 22 test files are empty `pass` classes. CI runs `bench run-tests` with zero actual tests
- **Priority tests:** CSL record_transfer/center_balance, stock ledger full-flow integration, payment status hook transitions
- **Priority:** HIGH | **Effort:** High

---

## PHASE 4: Scalability & Architecture

### 4.1 Sync Engine Pagination & Conflict Resolution
- **Problem:** `pull_changes()` returns ALL records since last sync with no pagination. No conflict detection — last-write-wins silently
- **Fix:** Add `page_size`/`page` params, implement timestamp conflict detection, move large syncs to `frappe.enqueue`
- **Priority:** HIGH | **Effort:** High

### 4.2 Center-Based Data Isolation (permission_query_conditions)
- **File:** `hooks.py:164-167` — `permission_query_conditions` is commented out
- **Fix:** Link Personnel to Center/Territory. Filter Purchases, Payments, Arrival Logs etc. by user's assigned center
- **Priority:** MEDIUM | **Effort:** High

### 4.3 CSL Summary/Balance Table
- **Problem:** Every stock balance check runs `SUM(CASE WHEN...)` over entire CSL table. Grows linearly with operations
- **Fix:** Create "Stock Balance" summary table updated incrementally on each CSL write. Use for balance checks; keep CSL for audit trail
- **Priority:** MEDIUM | **Effort:** High

---

## PHASE 5: Feature Expansion (New Capabilities)

### 5.1 Dashboard & Reporting Module
- **Problem:** No custom reports or dashboards exist beyond workspace number cards
- **Build:**
  - Center Operations Dashboard (daily arrivals, processing, dispatches, stock balances)
  - Purchase Analytics Report (by farmer, territory, date range, price trends)
  - Processing Yield Report (input vs output weight, efficiency %)
  - Stock Movement Report (CSL entries with IN/OUT/balance over time)
- **Priority:** HIGH | **Effort:** High

### 5.2 End-to-End Traceability / Lot Tracking
- **Problem:** No chain from green bean back to specific farmers. Required for EU Deforestation Regulation (EUDR) compliance
- **Build:** Traceability report: Green Bean Lot -> Secondary Processing -> Dispatch -> Primary Processing -> Arrival -> Purchase -> Farmer. Requires linking Primary Arrival to Purchases
- **Priority:** HIGH | **Effort:** High

### 5.3 Quality Grading & Cupping Scores
- **Problem:** Coffee grade is just a G1-G4 dropdown. No detailed quality assessment
- **Build:** "Coffee Quality Assessment" DocType: physical defects, screen size, moisture, SCA cupping scores (fragrance, acidity, body, etc.), final calculated grade
- **Priority:** MEDIUM | **Effort:** High

### 5.4 Farmer Payment Notifications (SMS)
- **Problem:** Payments recorded but farmers receive no confirmation
- **Build:** SMS notification on payment creation (Ethio Telecom gateway), printable PDF receipt for cash payments, farmer payment history view
- **Priority:** MEDIUM | **Effort:** Medium

### 5.5 Multi-Currency Support for Trades
- **Problem:** All values in implicit ETB. Export trades are priced in USD/EUR
- **Build:** Add currency field to Trades, leverage Frappe's Currency Exchange for conversion
- **Priority:** LOW | **Effort:** Medium

---

## Verification Plan

After each phase, verify with:
1. **Security fixes:** Test API endpoints as Guest/unauthenticated — `curl /api/resource/Purchases` should return 403
2. **Performance:** `EXPLAIN` CSL queries to confirm index usage; benchmark sync with 100+ records
3. **Validation:** Try creating invalid records (negative amounts, mismatched types) — should be rejected
4. **Tests:** `bench run-tests --app farmlink` should have passing tests after Phase 3.6
5. **Sync:** Full push/pull cycle with mobile app; verify no N+1 queries in MariaDB slow query log
6. **PWA:** Test offline access after service worker activation

---

## Summary Priority Matrix

| Priority | Items | Effort |
|----------|-------|--------|
| **CRITICAL** | Guest permissions, FIELD_MAPPINGS bug, sync security, CSL whitelist, sync commits, CSL indexes, server-side validation | Mixed (Low-High) |
| **HIGH** | Dead code cleanup, field type fixes, CSL caching, sync N+1, daily price, PWA, tests, dashboards, traceability, sync pagination | Mixed (Low-High) |
| **MEDIUM** | Trades completion, scheduler, harvest/fertilizer data, center isolation, CSL summary, quality grading, SMS notifications | Medium-High |
| **LOW** | Boot caching, module structure cleanup, multi-currency | Low-Medium |
