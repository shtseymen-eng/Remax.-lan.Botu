import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if getattr(sys, "frozen", False):
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")


def packaged_self_test():
    """Offline package check; never opens a user profile, account or messaging window."""
    from tempfile import TemporaryDirectory
    from PySide6.QtWidgets import QApplication, QWidget
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from playwright.sync_api import sync_playwright
    from remax_bot.core import DB
    app = QApplication([])
    window = QWidget()
    view = QWebEngineView()
    window.hide()
    app.processEvents()
    with TemporaryDirectory(prefix="remax-package-test-") as temp:
        assert DB(Path(temp) / "test.sqlite").all() == []
        with sync_playwright() as playwright:
            assert Path(playwright.chromium.executable_path).is_file(), "Bundled Chromium missing"
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(offline=True)
            page = context.new_page()
            page.set_content("<html><title>Offline package test</title><body>Ready</body></html>")
            assert page.title() == "Offline package test"
            context.close()
            browser.close()
    view.close()
    window.close()
    app.processEvents()
    print("Packaged offline Qt/SQLite/Chromium test passed.")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        packaged_self_test()
    else:
        from remax_bot.app import main
        main()
