# V12 Playwright Scanner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the failing QtWebEngine Sahibinden scanner with a visible Playwright/Chrome scanner while preserving the desktop UI and source-isolated database behavior.

**Architecture:** `playwright_scanner.py` owns browser automation and emits Qt signals from a background Python thread. `app.py` only controls start/resume/stop and commits a snapshot after full success. Parsing helpers are pure functions covered by unit tests.

**Tech Stack:** Python 3.11+, PySide6, QtWebEngine for WhatsApp/preview, Playwright sync API, SQLite, pytest.

**Spec:** `docs/superpowers/specs/2026-08-26-playwright-scanner-design.md`

## Global Constraints
- Windows and macOS remain supported.
- Chrome is visible during Sahibinden scanning.
- CAPTCHA/human verification is never bypassed automatically.
- A failed/partial scan never replaces existing source data.
- `TARA` scans only the selected source.

---

### Task 1: Parser and scan state
**Files:** Create `src/remax_bot/playwright_scanner.py`; Test `tests/test_playwright_scanner.py`.
- [ ] Write failing tests for total count, detail parsing, direct URL/id parsing, and verification detection.
- [ ] Run tests and confirm failure because module/functions do not exist.
- [ ] Implement pure parsing helpers and state primitives.
- [ ] Run tests and confirm pass.

### Task 2: Playwright worker
**Files:** Modify `src/remax_bot/playwright_scanner.py`.
- [ ] Implement visible persistent Chrome launch with Chromium fallback.
- [ ] Implement pagination/listing URL collection.
- [ ] Implement detail iteration with progress signals.
- [ ] Implement pause/resume/stop for human verification.

### Task 3: Desktop integration
**Files:** Modify `src/remax_bot/app.py`, `pyproject.toml`, `README.md`.
- [ ] Replace Qt Scanner binding with Playwright controller.
- [ ] Keep embedded preview tab but explain that scanning opens visible Chrome.
- [ ] Preserve source-isolated DB commit only on successful completion.
- [ ] Add Playwright dependency and install instructions.

### Task 4: Verification/package
- [ ] Run full pytest suite.
- [ ] Run Python compile check.
- [ ] Build V12 ZIP without caches.
