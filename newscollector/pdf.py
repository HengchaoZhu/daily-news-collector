"""Print HTML to PDF with Chromium (Playwright)."""

from __future__ import annotations

import os


def render_pdf(html: str) -> bytes:
    from playwright.sync_api import sync_playwright

    kwargs = {}
    exe = os.environ.get("PLAYWRIGHT_CHROMIUM_PATH")
    if exe:
        kwargs["executable_path"] = exe
    with sync_playwright() as p:
        browser = p.chromium.launch(**kwargs)
        page = browser.new_page()
        page.set_content(html, wait_until="load")
        pdf = page.pdf(format="A4", print_background=True,
                       margin={"top": "16mm", "bottom": "16mm", "left": "14mm", "right": "14mm"})
        browser.close()
    return pdf
