# Listing Deletion Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add confirmed permanent deletion for all, per-source, and selected listings while preserving stale-data cleanup only for complete trustworthy scans.

**Architecture:** Keep persistence and source reconciliation in `core.DB`; keep the PySide window responsible only for selection, confirmation, and refresh. Continue using the scanner's completeness validation and make the DB replacement boundary reject empty snapshots defensively.

**Tech Stack:** Python 3.11+, SQLite, PySide6, pytest, GitHub Actions/PyInstaller

**Spec:** `docs/superpowers/specs/2026-11-03-listing-deletion-management-design.md`

## Global Constraints

- Preserve the current UI design, WhatsApp Max engine, command behavior, scanner platforms, and all unrelated features.
- Every destructive UI action must show the exact affected count and require explicit confirmation with “No” as the safe default.
- Database changes must be permanent and transactional.
- Successful complete non-empty scans replace only their exact source; failed, partial, or suspiciously empty scans preserve prior data.
- Keep Windows EXE and macOS APP GitHub Actions packaging compatible; add no dependency.

## Review Focus

- Duplicate selected table cells/rows must delete each `(source_url, listing_id)` only once; Task 1 includes a deduplication test.
- Two sources with similar labels must remain isolated by normalized source URL; Task 1 includes a per-source isolation test.
- A zero-row snapshot must never clear a source; Task 2 includes a preservation test.
- A failure while inserting a replacement snapshot must roll back the preceding delete; Task 2 includes a transaction rollback test.
- Deleting the active filter's last advisor/source must not leave stale choices or counts; Task 3 verifies all deletion paths call the common refresh and rebuild source options.

---

### Task 1: Transactional Listing Deletion API

**Files:**
- Modify: `src/remax_bot/core.py`
- Modify: `tests/test_listing_management.py`

**Interfaces:**
- Produces: `DB.source_counts() -> list[tuple[str, int]]`
- Produces: `DB.delete_all() -> int`
- Produces: `DB.delete_source(source_url: str) -> int`
- Produces: `DB.delete_listings(identities: Iterable[tuple[str, str]]) -> int`

- [ ] **Step 1: Write failing DB tests**

Add tests named `test_source_counts_lists_real_normalized_sources`, `test_delete_source_is_permanent_and_keeps_other_sources`, `test_delete_selected_deduplicates_identities`, and `test_delete_all_returns_affected_count_and_clears_database`. Assert exact counts and remaining identities.

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `.venv/bin/python -m pytest tests/test_listing_management.py -q`

Expected: FAIL because the new DB methods do not exist.

- [ ] **Step 3: Implement the four DB methods**

Normalize every source through `source_key`, deduplicate selected identity pairs before `executemany`, execute each deletion within a SQLite context transaction, and return SQLite's actual deleted-row count.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/python -m pytest tests/test_listing_management.py -q`

Expected: PASS.

### Task 2: Safe Full-Scan Reconciliation Boundary

**Files:**
- Modify: `src/remax_bot/core.py`
- Modify: `tests/test_core.py`
- Modify: `tests/test_playwright_scanner.py`

**Interfaces:**
- Consumes: existing `DB.replace_source(source_url, items)` and `validate_scan_completeness(total, discovered, parsed)`
- Produces: `DB.replace_source` rejects an empty snapshot before opening a destructive transaction, while preserving atomic complete replacement for non-empty snapshots.

- [ ] **Step 1: Write failing reconciliation tests**

Add `test_replace_source_removes_stale_rows_after_complete_snapshot`, `test_replace_source_rejects_empty_snapshot_and_preserves_existing_rows`, and `test_replace_source_rolls_back_when_snapshot_insert_fails`. Retain the scanner completeness assertions for unknown totals and mismatched discovered/parsed counts.

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `.venv/bin/python -m pytest tests/test_core.py tests/test_playwright_scanner.py -q`

Expected: the empty-snapshot preservation test FAILS because current `replace_source` deletes the source.

- [ ] **Step 3: Add the defensive non-empty guard**

Materialize `items` once, raise `ValueError` with a data-preservation message when it is empty, and leave the existing single-transaction delete/insert replacement intact.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/python -m pytest tests/test_core.py tests/test_playwright_scanner.py -q`

Expected: PASS.

### Task 3: Confirmed Deletion Controls and Refresh

**Files:**
- Modify: `src/remax_bot/app.py`
- Modify: `tests/test_ui_contract.py`

**Interfaces:**
- Consumes: Task 1 DB methods and existing `Main.refresh()` / table identity data.
- Produces: `Main.delete_all_listings()`, `Main.delete_source_listings()`, `Main.delete_selected_listings()`, `_confirm_listing_delete(...)`, `_selected_listing_identities()`, and `_refresh_delete_sources()`.

- [ ] **Step 1: Write failing UI contract tests**

Assert extended row selection, button texts `TÜM İLANLARI SİL`, `KAYNAĞI SİL`, `SEÇİLİ İLANLARI SİL`, a real-source combo populated from `db.source_counts()`, `QMessageBox.question` with a count-bearing message and `No` default, calls to the corresponding DB methods, and `refresh()` after success.

- [ ] **Step 2: Run the UI contract test and verify failure**

Run: `.venv/bin/python -m pytest tests/test_ui_contract.py -q`

Expected: FAIL because deletion controls and handlers do not exist.

- [ ] **Step 3: Implement controls and handlers**

Add a compact deletion action row in the existing listing card, set tables to extended row selection, preserve the selected deletion source across refreshes, calculate counts from the DB at action time, default confirmation to No, delete only after Yes, clear remembered selection, and call the existing common refresh path.

- [ ] **Step 4: Run UI and listing tests**

Run: `.venv/bin/python -m pytest tests/test_ui_contract.py tests/test_listing_management.py -q`

Expected: PASS.

### Task 4: Documentation and Cross-Platform Regression Verification

**Files:**
- Modify: `README.md`
- Verify unchanged: `.github/workflows/main.yml`

**Interfaces:**
- Consumes: Tasks 1–3 behavior.
- Produces: user instructions describing the three deletion paths and safe source refresh behavior.

- [ ] **Step 1: Update the README**

Document selecting multiple rows, deleting a real source, deleting all records, count/confirmation behavior, and the complete-scan-only stale cleanup rule.

- [ ] **Step 2: Run the complete test suite**

Run: `.venv/bin/python -m pytest -q`

Expected: all tests PASS.

- [ ] **Step 3: Verify packaging-sensitive imports and workflow diff**

Run: `.venv/bin/python -m compileall -q src launcher.py && git diff --check && git diff -- .github/workflows/main.yml`

Expected: compile and whitespace checks succeed; workflow diff is empty.

- [ ] **Step 4: Review final diff**

Run: `git status --short && git diff --stat && git diff`

Expected: only planned source, test, documentation, spec, and plan files changed; no generated build artifacts.
