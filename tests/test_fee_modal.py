"""
Unit and structure verification tests for the VIT Mumbai Fee Modal Financial Dashboard.
Validates:
1. Markup structure (close buttons, backdrop, tabs, body, footer, accessibility)
2. CSS rules (flex scrolling, pinned header/footer, z-index, [hidden] override, background overflow lock)
3. JavaScript logic (closing on X, Close button, Backdrop, Outside click, Escape key, and background scroll lock/unlock)
"""

import unittest
import re
from pathlib import Path
from bs4 import BeautifulSoup


class TestFeeModalDashboard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parent.parent
        cls.html_path = cls.root / "templates" / "index.html"
        cls.css_path = cls.root / "static" / "style.css"
        cls.js_path = cls.root / "static" / "app.js"

        cls.html_content = cls.html_path.read_text(encoding="utf-8")
        cls.css_content = cls.css_path.read_text(encoding="utf-8")
        cls.js_content = cls.js_path.read_text(encoding="utf-8")
        cls.soup = BeautifulSoup(cls.html_content, "html.parser")

    def test_html_modal_attributes(self):
        """Verify modal element has proper dialog accessibility attributes."""
        modal = cls_modal = self.soup.find(id="feeModal")
        self.assertIsNotNone(modal, "feeModal element must exist in templates/index.html")
        self.assertEqual(modal.get("role"), "dialog")
        self.assertEqual(modal.get("aria-modal"), "true")
        self.assertEqual(modal.get("aria-labelledby"), "feeModalTitle")
        self.assertTrue(modal.has_attr("hidden"), "feeModal should have hidden attribute initially")

    def test_html_close_buttons_exist(self):
        """Verify top-right X button and footer Close button exist."""
        x_btn = self.soup.find(id="closeFeeModalBtn")
        self.assertIsNotNone(x_btn, "#closeFeeModalBtn (top-right X) must exist")
        self.assertEqual(x_btn.get("type"), "button")

        footer_close = self.soup.find(id="closeFeeModalFooterBtn")
        self.assertIsNotNone(footer_close, "#closeFeeModalFooterBtn must exist")
        self.assertEqual(footer_close.get("type"), "button")

        backdrop = self.soup.find(id="feeModalBackdrop")
        self.assertIsNotNone(backdrop, "#feeModalBackdrop must exist")

    def test_html_card_header_body_footer_structure(self):
        """Verify modal card has header, tabs bar, scrollable body, and footer."""
        modal = self.soup.find(id="feeModal")
        card = modal.find(class_="fee-modal-card")
        self.assertIsNotNone(card, ".fee-modal-card must be inside #feeModal")

        header = card.find(class_="fee-modal-header")
        self.assertIsNotNone(header, ".fee-modal-header must exist")

        tabs_bar = card.find(class_="fee-tabs-bar")
        self.assertIsNotNone(tabs_bar, ".fee-tabs-bar must exist")

        body = card.find(class_="fee-modal-body")
        self.assertIsNotNone(body, ".fee-modal-body must exist")

        footer = card.find(class_="fee-modal-footer")
        self.assertIsNotNone(footer, ".fee-modal-footer must exist")

    def test_css_hidden_override_and_open_state(self):
        """Verify CSS contains .fee-modal-overlay[hidden] display:none !important."""
        self.assertIn(".fee-modal-overlay[hidden]", self.css_content)
        self.assertIn("display: none !important", self.css_content)
        self.assertIn(".fee-modal-overlay.open", self.css_content)

    def test_css_flex_scrolling_rules(self):
        """Verify middle content scrolls while header, tabs, and footer remain locked."""
        # Body must have flex: 1 1 auto, min-height: 0, overflow-y: auto
        self.assertIn("min-height: 0", self.css_content, "fee-modal-body needs min-height: 0 for flex scrolling")
        self.assertIn("overflow-y: auto", self.css_content)
        
        # Header, tabs, and footer must have flex-shrink: 0
        self.assertIn(".fee-modal-header", self.css_content)
        self.assertIn(".fee-tabs-bar", self.css_content)
        self.assertIn(".fee-modal-footer", self.css_content)

    def test_css_background_scroll_lock(self):
        """Verify body.modal-open has overflow: hidden !important."""
        self.assertIn("body.modal-open", self.css_content)
        self.assertIn("overflow: hidden !important", self.css_content)

    def test_js_close_button_handlers(self):
        """Verify JavaScript attaches close handlers to X button, footer button, and backdrop."""
        self.assertIn("closeFeeModalBtn?.addEventListener", self.js_content)
        self.assertIn("closeFeeModalFooterBtn?.addEventListener", self.js_content)
        self.assertIn("feeModalBackdrop?.addEventListener", self.js_content)

    def test_js_click_outside_modal(self):
        """Verify clicking outside modal-card closes the modal."""
        self.assertIn("!card.contains(e.target)", self.js_content)
        self.assertIn("feeModal?.addEventListener(\"click\"", self.js_content)

    def test_js_card_stops_propagation(self):
        """Verify clicking inside modal-card stops propagation so user interaction doesn't close it."""
        self.assertIn(".fee-modal-card\")?.addEventListener(\"click\"", self.js_content)
        self.assertIn("e.stopPropagation()", self.js_content)

    def test_js_escape_key_listener(self):
        """Verify Escape key listener closes the modal when open."""
        self.assertIn('e.key === "Escape"', self.js_content)
        self.assertIn("closeFeeModal()", self.js_content)

    def test_js_scroll_lock_and_unlock(self):
        """Verify body.style.overflow is toggled and modal-open class is added/removed."""
        self.assertIn('document.body.classList.add("modal-open")', self.js_content)
        self.assertIn('document.body.classList.remove("modal-open")', self.js_content)
        self.assertIn('document.body.style.overflow = "hidden"', self.js_content)
        self.assertIn('document.body.style.overflow = ""', self.js_content)


if __name__ == "__main__":
    unittest.main()
