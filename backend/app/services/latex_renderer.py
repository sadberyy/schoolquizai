from playwright.sync_api import sync_playwright


def render_latex_to_png(latex: str) -> bytes:
    """Рендеринг Latex-формул в PNG через Playwright + KaTeX"""
    # спецсимволы для HTML
    latex_escaped = latex.replace('\\', '\\\\')
    
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
                katex.render("{latex_escaped}", document.getElementById("formula"), {{
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
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 800, "height": 100})
        page.set_content(html, wait_until="networkidle")
        
        page.wait_for_selector("#formula", state="attached")
        
        element = page.locator("#formula")
        screenshot = element.screenshot(type="png")
        
        browser.close()
        return screenshot