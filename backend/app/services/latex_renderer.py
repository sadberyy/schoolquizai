import io
import json
import logging

logger = logging.getLogger(__name__)

_KATEX_CDN = "https://cdn.jsdelivr.net/npm/katex@0.16.9/dist"


def render_latex_to_png(latex: str) -> bytes | None:
    """
    Рендеринг LaTeX в PNG через Playwright + KaTeX (CDN), как в рабочем latex_renderer.
    """
    if not latex or not str(latex).strip():
        return None

    latex_js = json.dumps(str(latex).strip())

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <link rel="stylesheet" href="{_KATEX_CDN}/katex.min.css">
        <script src="{_KATEX_CDN}/katex.min.js"></script>
        <script src="{_KATEX_CDN}/contrib/mhchem.min.js"></script>
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
    </body>
    </html>
    """

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("playwright not installed")
        return _render_latex_matplotlib(latex)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 800, "height": 100})
                page.set_content(html, wait_until="networkidle", timeout=90_000)
                page.wait_for_function(
                    "() => typeof katex !== 'undefined'",
                    timeout=60_000,
                )
                page.evaluate(
                    f"""
                    () => {{
                        katex.render({latex_js}, document.getElementById("formula"), {{
                            throwOnError: true,
                            displayMode: false
                        }});
                    }}
                    """
                )
                page.wait_for_selector("#formula .katex", state="attached", timeout=30_000)
                return page.locator("#formula").screenshot(type="png")
            finally:
                browser.close()
    except Exception as e:
        logger.warning("render_latex_to_png failed: %s", e, exc_info=False)

    return _render_latex_matplotlib(latex)


def _render_latex_matplotlib(latex: str) -> bytes | None:
    """Fallback, если Playwright/Chromium или CDN недоступны."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    expr = str(latex).strip()
    if not expr:
        return None

    fig = plt.figure(figsize=(4, 0.6))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    try:
        ax.text(0.5, 0.5, f"${expr}$", fontsize=14, ha="center", va="center")
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=160, bbox_inches="tight", pad_inches=0.08, transparent=True)
        return buf.getvalue() or None
    except Exception as e:
        logger.warning("_render_latex_matplotlib failed: %s", e, exc_info=False)
        return None
    finally:
        plt.close(fig)
