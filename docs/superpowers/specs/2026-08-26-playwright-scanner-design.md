# V12 Playwright Scanner Design

V12 keeps the PySide6 desktop UI and embedded WhatsApp Web tab, but removes Sahibinden scraping from QtWebEngine. The `TARA` action launches a visible installed Google Chrome browser through Playwright using a dedicated persistent profile. This profile preserves login/cookies between runs without interfering with the user's normal Chrome profile.

Each configured source is scanned independently. A successful scan replaces only that source's records in SQLite. A partial, stopped, verification-blocked, or failed scan never deletes the source's existing records. The scanner collects all listing URLs across pagination, then visits every listing and extracts listing id, title, direct URL, advisor/owner name, visible phone, price, location, rooms, square metres, transaction/property type, and listing date.

If human verification is detected, the browser remains visible and the scan pauses. The desktop `DEVAM ET` action resumes the same worker. `DURDUR` aborts safely. Progress is emitted as `completed / total` after each complete detail record.
