"""
Unit & Integration Tests for Light / Dark Theme Feature
"""
import unittest
from pathlib import Path


class ThemeFeatureTestCase(unittest.TestCase):
    def setUp(self):
        self.base_dir = Path(__file__).resolve().parent.parent
        self.index_html_path = self.base_dir / "templates" / "index.html"
        self.style_css_path = self.base_dir / "static" / "style.css"
        self.app_js_path = self.base_dir / "static" / "app.js"

        self.index_html = self.index_html_path.read_text(encoding="utf-8")
        self.style_css = self.style_css_path.read_text(encoding="utf-8")
        self.app_js = self.app_js_path.read_text(encoding="utf-8")

    def test_meta_color_scheme_and_fouc_script_in_html(self):
        """Verify modern color-scheme meta and FOUC prevention inline script exist in head."""
        self.assertIn('<meta name="color-scheme" content="light dark">', self.index_html)
        self.assertIn('localStorage.getItem("theme")', self.index_html)
        self.assertIn('document.documentElement.setAttribute("data-theme"', self.index_html)

    def test_theme_toggle_buttons_in_html(self):
        """Verify theme toggle button exists in both topbar and sidebar drawer."""
        self.assertIn('id="themeToggleBtn"', self.index_html)
        self.assertIn('id="sidebarThemeToggleBtn"', self.index_html)
        self.assertIn('theme-icon-sun', self.index_html)
        self.assertIn('theme-icon-moon', self.index_html)

    def test_css_design_tokens_and_color_scheme(self):
        """Verify CSS contains color-scheme: light dark and dark mode token mappings."""
        self.assertIn("color-scheme: light dark;", self.style_css)
        self.assertIn(':root:has(> head > meta[name="color-scheme"][content="dark"])', self.style_css)
        self.assertIn(':root:has(> head > meta[name="color-scheme"][content="light"])', self.style_css)
        self.assertIn('[data-theme="dark"]', self.style_css)
        self.assertIn("@media (prefers-color-scheme: dark)", self.style_css)
        self.assertIn("--composer-fade:", self.style_css)

    def test_javascript_theme_controller(self):
        """Verify JavaScript contains theme resolution, switching, and sync listeners."""
        self.assertIn('const THEME_STORAGE_KEY = "theme"', self.app_js)
        self.assertIn("function getResolvedTheme()", self.app_js)
        self.assertIn("function setTheme(", self.app_js)
        self.assertIn("function toggleTheme()", self.app_js)
        self.assertIn('window.addEventListener("storage"', self.app_js)
        self.assertIn('window.matchMedia("(prefers-color-scheme: dark)")', self.app_js)


if __name__ == "__main__":
    unittest.main()
