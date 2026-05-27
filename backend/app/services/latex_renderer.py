import json
import logging

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


def render_latex_to_png(latex: str) -> bytes | None:
    """
    Рендеринг LaTeX в PNG через Playwright + KaTeX (+ mhchem).
    При ошибке (нет браузера, сеть, невалидный LaTeX) возвращает None — не бросает исключение наружу.
    """
    if not latex or not str(latex).strip():
        return None

    latex_js = json.dumps(str(latex).strip())

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
        <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/mhchem.min.js"></script>
        <style>
            body {{
                margin: 0;
                padding: 2px 4px;
                display: inline-block;
                font-size: 14px;
                background: white;
            }}
        </style>
    </head>
    <body>
        <div id="formula"></div>
        <script>
            try {{
                katex.render({latex_js}, document.getElementById("formula"), {{
                    throwOnError: true,
                    displayMode: false
                }});
            }} catch(e) {{
                document.getElementById("formula").textContent = "LaTeX Error: " + e.message;
            }}
        </script>
    </body>
    </html>
    """

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 800, "height": 200})
                page.set_content(html, wait_until="domcontentloaded", timeout=90_000)
                page.wait_for_selector("#formula", state="attached", timeout=60_000)
                element = page.locator("#formula")
                return element.screenshot(type="png")
            finally:
                browser.close()
    except Exception as e:
        logger.warning("render_latex_to_png failed: %s", e, exc_info=False)
        return None
