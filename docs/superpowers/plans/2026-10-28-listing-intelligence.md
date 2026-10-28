# İlan Ayrıntıları ve Max Arama Ayarları Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sahibinden Excel/CSV verilerini, Emlakjet ve MyRE/MAX taramalarını ayrıntılı ve adresli tek ilan havuzunda birleştirip Max aramasını Ayarlar'dan yönetilebilir hâle getirmek.

**Architecture:** Mevcut `Listing` ve SQLite deposu geriye uyumlu sabit alanlarla genişletilecek; kategoriye özgü alanlar JSON ayrıntı sözlüğünde korunacak. İçe/dışa aktarma aynı modeli Excel ve CSV'ye kayıpsız taşıyacak, tarayıcılar detay sayfasındaki etiket-değer çiftlerini modele verecek, Max ise seçilen kaynak ve alanlarda arama yapacak. Mevcut WhatsApp taşıma/okuma katmanı korunacak; yalnızca komut işareti bağımlılığı enjekte edilecek.

**Tech Stack:** Python 3.12+, dataclasses, SQLite, PySide6, Playwright, openpyxl, CSV, pytest, PyInstaller, GitHub Actions

**Spec:** `docs/superpowers/specs/2026-10-28-listing-intelligence-design.md`

## Global Constraints

- Mevcut arayüz düzeni, marka görünümü ve WhatsApp okuma/gönderme davranışı yeniden tasarlanmayacak.
- Adres veya ilan özelliği kaynakta yoksa tahmin edilmeyecek; boş kalacak.
- Eski SQLite, ayar, Excel ve CSV verileri kayıpsız ve varsayılanlarla çalışmaya devam edecek.
- Normal Max sonuçları `ilan` veya `link` kelimesi olmasa da her zaman ilan bağlantısını içerecek.
- `danışmanlar` komutu arama alanı ayarlarından bağımsız olarak üç platformun tamamını karşılaştıracak.
- GitHub Actions mevcut Windows EXE ve macOS APP işlerini koruyacak; derlenmiş paketler repoya commit edilmeyecek.

## Review Focus

- Eski 13 alanlı SQLite tablosu yükseltilirken mevcut ilanların veya danışman takma adlarının kaybolmaması — Task 1 göç testi.
- Boş/bozuk `details_json` değerinin ilan listesini bozmayıp boş ayrıntı olarak okunması — Task 1 dayanıklılık testi.
- Tanınmayan Excel/CSV sütunlarının kaybolmadan dinamik ayrıntı olarak gidiş-dönüş yapması — Task 2 gidiş-dönüş testleri.
- Bir otomatik tarama başarısızken içe aktarılan Sahibinden verisi ile diğer kaynakların eski verisinin korunması ve sıranın devam etmesi — Task 5 kuyruk testleri.
- Değiştirilen komut işaretinin eski `#` mesajlarını yanlışlıkla komut saymaması, varsayılan `#` kurulumların ise aynen çalışması — Task 4 yönlendirme testleri.

---

### Task 1: Ayrıntılı ilan modeli ve kayıpsız SQLite yükseltmesi

**Files:**
- Create: `src/remax_bot/listing_details.py`
- Modify: `src/remax_bot/core.py`
- Create: `tests/test_listing_details.py`
- Modify: `tests/test_core.py`

**Interfaces:**
- Produces: `Listing(..., province="", district="", neighborhood="", street="", complex_name="", full_address="", description="", net_sqm="", details=dict)`; all new fields append after existing `source_url` positional field.
- Produces: `normalize_details(value) -> dict[str, str]`, `details_text(details) -> str`, `display_address(item: Listing) -> str`.
- Produces: `search(items, query, fields=None) -> list[Listing]`, where `fields=None` preserves all-field default behavior and named fields restrict the searchable haystack.

- [ ] **Step 1: Write failing model, address, search, migration, and malformed-JSON tests**

Add tests proving that known address components render in order without invented parts; description/dynamic details are searchable only when enabled; an old schema row survives `DB(...)`; and malformed JSON becomes `{}` without losing the row.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_listing_details.py tests/test_core.py -q`

Expected: FAIL because the new fields/helpers and schema columns do not exist.

- [ ] **Step 3: Implement normalization helpers and append the new `Listing` fields**

Use deterministic whitespace cleanup, non-empty string keys/values, stable JSON serialization, and a display address assembled only from non-empty known fields.

- [ ] **Step 4: Implement additive SQLite migration and explicit row serialization**

Add missing columns with `ALTER TABLE` rather than rebuilding a current database. Centralize row-to-`Listing` and `Listing`-to-row conversion so `replace_source`, `upsert`, `update_listing`, `raw_listing`, and `all` use the same field order and JSON handling.

- [ ] **Step 5: Extend editable fields and configurable search**

Keep legacy `location`; add the address, description, net m², and details fields. Map search field names to exact model values and include dynamic detail keys and values only for the `details` selection.

- [ ] **Step 6: Run focused and full tests, then commit**

Run: `.venv/bin/python -m pytest tests/test_listing_details.py tests/test_core.py -q`

Run: `.venv/bin/python -m pytest -q`

Commit: `feat: extend listing details and storage`

### Task 2: Kayıpsız Excel/CSV sözleşmesi ve yapay zekâ şablonu

**Files:**
- Modify: `src/remax_bot/importer.py`
- Create: `tests/test_listing_file_details.py`
- Modify: `tests/test_listing_management.py`

**Interfaces:**
- Consumes: Task 1 extended `Listing` and `normalize_details`.
- Produces: `read_list_file(path) -> list[Listing]` preserving unknown non-empty columns in `Listing.details`.
- Produces: `write_list_file(path, items) -> Path` supporting `.xlsx` and UTF-8 BOM `.csv`.
- Produces: `write_ai_template(path) -> Path` with the fixed Turkish columns and an instruction sheet for XLSX.

- [ ] **Step 1: Write failing XLSX/CSV and template tests**

Test fixed address fields, Turkish characters, unknown fields such as `Isıtma` and `Bulunduğu Kat`, hyperlinks, empty values, and old `Bölge` input. Assert an exported file re-imports to equivalent listings and dynamic details.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_listing_file_details.py tests/test_listing_management.py -q`

Expected: FAIL because new aliases, CSV output, dynamic columns, and template creation are absent.

- [ ] **Step 3: Extend header aliases and dynamic column import**

Map the exact Turkish fixed headers from the spec. Treat every other non-empty column as a detail key, excluding fully blank columns and recognized aliases.

- [ ] **Step 4: Implement XLSX and CSV export from one canonical row builder**

Output fixed columns first, then the sorted union of dynamic detail keys. Preserve the existing blue XLSX header and hyperlink behavior; write CSV with `utf-8-sig` and a stable delimiter readable by the existing sniffer.

- [ ] **Step 5: Implement the AI template generator**

Create an `İlanlar` sheet with headers only and an `Alan Açıklamaları` sheet stating that only `İlan Linki` is mandatory, missing values must remain blank, and additional source fields may be appended as columns.

- [ ] **Step 6: Run focused and full tests, then commit**

Run: `.venv/bin/python -m pytest tests/test_listing_file_details.py tests/test_listing_management.py -q`

Run: `.venv/bin/python -m pytest -q`

Commit: `feat: preserve listing details in spreadsheet files`

### Task 3: Üç platformun detay ve adres çıkarımı

**Files:**
- Modify: `src/remax_bot/playwright_scanner.py`
- Modify: `src/remax_bot/remax_web_scanner.py`
- Modify: `tests/test_playwright_scanner.py`
- Modify: `tests/test_emlakjet_scanner.py`
- Modify: `tests/test_remax_direct_scanner.py`
- Modify: `tests/test_shadow_card_scanner.py`

**Interfaces:**
- Consumes: Task 1 extended `Listing`.
- Produces: `normalize_detail_pairs(pairs) -> dict[str, str]` and `PlaywrightScanner._read_detail_attributes(page) -> dict[str, str]`.
- Updates: `parse_remax_detail(..., details=None)`, `parse_emlakjet_detail(..., details=None)`, and `parse_listing_detail(..., details=None)` while keeping old calls valid.

- [ ] **Step 1: Write failing realistic parser tests for each platform**

Use literal page-text and label/value fixtures. Verify province, district, neighborhood, street, site, explicit full address, description, gross/net m², and category-specific details. Include missing-component cases that must remain empty.

- [ ] **Step 2: Run scanner tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_playwright_scanner.py tests/test_emlakjet_scanner.py tests/test_remax_direct_scanner.py tests/test_shadow_card_scanner.py -q`

Expected: FAIL because parsers currently return only general location and one m² value.

- [ ] **Step 3: Extract structured label/value pairs from real detail DOM boundaries**

Read table rows, `dt/dd`, list items, and two-part feature blocks without accepting navigation/sidebar text. Normalize duplicate labels deterministically; keep the first meaningful value and ignore empty pairs.

- [ ] **Step 4: Populate canonical fields without guessing**

Prefer explicit detail labels and breadcrumbs. Use platform-specific known structures only; do not infer street/site from title or description. Store all remaining pairs in `details` and extract description only from the detail description container/text section.

- [ ] **Step 5: Update the embedded MyRE/MAX scanner payload**

Return the same canonical address/detail keys from `DETAIL_JS` and pass them into the extended `Listing` constructor, leaving Shadow DOM traversal and card navigation unchanged.

- [ ] **Step 6: Run scanner and full tests, then commit**

Run: `.venv/bin/python -m pytest tests/test_playwright_scanner.py tests/test_emlakjet_scanner.py tests/test_remax_direct_scanner.py tests/test_shadow_card_scanner.py -q`

Run: `.venv/bin/python -m pytest -q`

Commit: `feat: capture detailed listing data from every source`

### Task 4: Ayarlanabilir Max komut ve arama motoru

**Files:**
- Create: `src/remax_bot/settings_schema.py`
- Modify: `src/remax_bot/importer.py`
- Modify: `src/remax_bot/whatsapp_webengine.py`
- Modify: `src/remax_bot/whatsapp_playwright.py`
- Modify: `tests/test_commands.py`
- Modify: `tests/test_listing_features.py`
- Modify: `tests/test_whatsapp_embedded_runtime.py`
- Modify: `tests/test_whatsapp_playwright_runtime.py`
- Modify: `tests/test_whatsapp_reader_compat.py`

**Interfaces:**
- Produces: `DEFAULT_SEARCH_SOURCES`, `DEFAULT_SEARCH_FIELDS`, `normalize_command_prefix(value)`, and settings normalization helpers.
- Updates: `parse_command(text, prefix="#")`, `command_help(prefix="#")`, `command_response(items, text, limit=12, link_source=None, prefix="#", search_sources=None, search_fields=None)`.
- Produces: `max_intro(prefix="#")`, `max_stopped(prefix="#")`; legacy `MAX_INTRO` remains the default-`#` value.
- Updates: `classify_command(text, prefix="#")`, `MessageRouter(..., command_prefix="#")`, and external/embedded bot constructors with default-compatible prefix injection.

- [ ] **Step 1: Write failing prefix, selected-source, selected-field, ranking, and unconditional-link tests**

Cover default `#`, custom `!`, rejection of the old prefix after customization, source subsets, disabled description/details, advisor/address prioritization, and links without `ilan`/`link` tokens. Verify `danışmanlar` still compares all platforms regardless of the normal search selections.

- [ ] **Step 2: Run command and WhatsApp router tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_commands.py tests/test_listing_features.py tests/test_whatsapp_embedded_runtime.py tests/test_whatsapp_playwright_runtime.py tests/test_whatsapp_reader_compat.py -q`

Expected: FAIL because prefix and field/source configuration are not accepted.

- [ ] **Step 3: Implement settings defaults and configurable command parsing**

Allow one visible non-whitespace prefix character, falling back to `#`. Generate help/start/stop text from the saved prefix while retaining default constants for existing callers.

- [ ] **Step 4: Implement selected-field search and deterministic relevance ordering**

Require every query token to occur in at least one enabled field. Rank exact/earlier matches in address, title, and advisor ahead of description and dynamic details; retain existing price ceiling ordering when a price is supplied.

- [ ] **Step 5: Inject the prefix into routers without changing browser behavior**

Update only classification/status/reply text. Do not edit WhatsApp DOM scripts, snapshot format, chat locking, deduplication, send queue, composer, or profile lifecycle.

- [ ] **Step 6: Run focused and full tests, then commit**

Run: `.venv/bin/python -m pytest tests/test_commands.py tests/test_listing_features.py tests/test_whatsapp_embedded_runtime.py tests/test_whatsapp_playwright_runtime.py tests/test_whatsapp_reader_compat.py -q`

Run: `.venv/bin/python -m pytest -q`

Commit: `feat: make max listing search configurable`

### Task 5: Ayarlar arayüzü, adres görünümü ve otomatik tarama kuyruğu

**Files:**
- Modify: `src/remax_bot/app.py`
- Modify: `tests/test_ui_contract.py`
- Create: `tests/test_auto_scan_queue.py`

**Interfaces:**
- Consumes: Tasks 1-4 model, file, search, and prefix interfaces.
- Produces: application methods `_start_auto_scan_queue()`, `_scan_next_queued_source()`, `_complete_current_scan(success)` with at most one active Playwright scan.

- [ ] **Step 1: Write failing UI contract and queue behavior tests**

Assert the existing navigation, WhatsApp card, data movement controls, and branding remain. Add checks for Max settings, source/field checkboxes, command prefix, template button, Excel/CSV save filter, address column, and queue order. Simulate success/failure transitions with a small fake scanner so failure advances without replacing stored data.

- [ ] **Step 2: Run UI/queue tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_ui_contract.py tests/test_auto_scan_queue.py -q`

Expected: FAIL because settings widgets, address display, template action, and queue methods do not exist.

- [ ] **Step 3: Add backward-compatible defaults and Max settings controls**

Persist command prefix, selected search sources/fields, auto-scan toggle, and selected automatic sources. Missing keys in old JSON receive the design defaults. Saving settings immediately updates command help, Bot Testi, and the running router prefix.

- [ ] **Step 4: Extend existing listing/data controls without redesign**

Add one `Adres` display column, extended editor fields, `.xlsx/.csv` export selection, and `YAPAY ZEKÂ EXCEL ŞABLONU` action. Adjust stored link-column indices so double-click navigation still opens the correct URL.

- [ ] **Step 5: Implement sequential post-import scanning**

After successful file import, enqueue only selected MyRE/MAX/Emlakjet labels. Reuse the existing scanner signals. Each successful source replaces only itself; each failure leaves old rows intact, reports the error, and advances to the next selected source.

- [ ] **Step 6: Pass settings into Bot Testi and ExternalWhatsAppBot**

Use the same prefix, source, and field selection in both test and real WhatsApp paths. Do not keep the old single-source combo as a hidden conflicting filter; migrate its value only when helpful for old settings.

- [ ] **Step 7: Run focused and full tests, then commit**

Run: `.venv/bin/python -m pytest tests/test_ui_contract.py tests/test_auto_scan_queue.py -q`

Run: `.venv/bin/python -m pytest -q`

Commit: `feat: add max search settings and automatic scans`

### Task 6: Örnek dosya, sürüm, dokümantasyon ve çift platform teslimatı

**Files:**
- Modify: `README.md`
- Modify: `KURULUM.txt`
- Modify: `pyproject.toml`
- Modify: `src/remax_bot/__init__.py`
- Verify: `.github/workflows/main.yml`
- Create deliverable: `outputs/REMAX_Sahibinden_AI_Sablonu.xlsx`

**Interfaces:**
- Consumes: Task 2 `write_ai_template`.
- Produces: version `0.42.0` consistently in package metadata and application.

- [ ] **Step 1: Update documentation and version tests first**

Document the external-AI Excel flow, address/detail rules, Settings options, automatic scan order, custom command examples, unconditional links, CSV export, and where GitHub Actions artifacts are downloaded. Update the existing version-consistency test expectation through behavior/metadata comparison rather than source-only duplication.

- [ ] **Step 2: Generate and inspect the user-facing XLSX template using the spreadsheet workflow**

Run the production template generator to create `outputs/REMAX_Sahibinden_AI_Sablonu.xlsx`. Open/recalculate/inspect it with the spreadsheet tooling and confirm headers, instruction sheet, widths, freeze panes, filters, and Turkish characters.

- [ ] **Step 3: Verify package workflow contracts**

Confirm `.github/workflows/main.yml` still has independent `windows-latest` and `macos-latest` jobs, runs the full tests before packaging, uploads the Windows `dist/REMAX_Ilan_Botu/` directory, and uploads `REMAX_Ilan_Botu_macOS.zip`. Change the workflow only if verification exposes a packaging gap.

- [ ] **Step 4: Run fresh final verification**

Run: `.venv/bin/python -m pytest -q`

Run: `.venv/bin/python -m compileall -q src launcher.py`

Run: `git diff --check`

Expected: all tests pass, compile exits 0, and no whitespace errors.

- [ ] **Step 5: Commit and publish through GitHub**

Commit: `release: prepare listing intelligence 0.42.0`

Push the feature branch, open a pull request, attach it to this task, review the complete diff, and merge only after all repository checks are successful. The merge to `main` triggers both Windows EXE and macOS APP jobs.

- [ ] **Step 6: Verify GitHub Actions artifacts**

Wait for both build jobs. Confirm `REMAX-Ilan-Botu-Windows` and `REMAX-Ilan-Botu-macOS` artifacts are present. If a build fails, read its diagnostics, fix through TDD, and repeat verification before claiming delivery.
