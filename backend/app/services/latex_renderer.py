import io
import json
import logging
import threading
from contextlib import contextmanager
from functools import lru_cache

from app.services.formula_export import _PX_PER_PT

logger = logging.getLogger(__name__)

# CDN надёжнее file:// + set_content на Windows/Chromium.
_KATEX_CDN = "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist"

_CHROMIUM_ARGS = [
    "--disable-gpu",
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--single-process",
    "--max_old_space_size=64",
]

_BATCH_LOCAL = threading.local()
_PLAYWRIGHT_LOCK = threading.Lock()


def _shell_html(font_size_px: float) -> str:
    return f"""
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
                font-size: {font_size_px:.2f}px;
                background: white;
            }}
        </style>
    </head>
    <body>
        <div id="formula"></div>
    </body>
    </html>
    """


class _PlaywrightLatexSession:
    """Один Chromium + KaTeX на весь экспорт (PDF/PPTX/DOCX)."""

    def __init__(self) -> None:
        self._pw_cm = None
        self._browser = None
        self._page = None
        self._ready = False
        self._font_size_px = 14.0

    def start(self, font_size_px: float = 14.0) -> bool:
        if self._ready and abs(self._font_size_px - font_size_px) < 0.01:
            return True
        if self._ready:
            self.stop()

        try:
            from playwright.sync_api import sync_playwright

            with _PLAYWRIGHT_LOCK:
                self._pw_cm = sync_playwright()
                playwright = self._pw_cm.__enter__()
                self._browser = playwright.chromium.launch(headless=True, args=_CHROMIUM_ARGS)
                self._page = self._browser.new_page(viewport={"width": 800, "height": 200})
                self._font_size_px = font_size_px
                self._page.set_content(
                    _shell_html(font_size_px),
                    wait_until="networkidle",
                    timeout=60_000,
                )
                self._page.wait_for_function(
                    "() => typeof katex !== 'undefined'",
                    timeout=30_000,
                )
            self._ready = True
            return True
        except Exception as e:
            logger.warning("Playwright session start failed: %s", e, exc_info=True)
            self.stop()
            return False

    def stop(self) -> None:
        with _PLAYWRIGHT_LOCK:
            if self._browser is not None:
                try:
                    self._browser.close()
                except Exception as e:
                    logger.debug("browser.close failed: %s", e)
                self._browser = None
            if self._pw_cm is not None:
                try:
                    self._pw_cm.__exit__(None, None, None)
                except Exception as e:
                    logger.debug("playwright.__exit__ failed: %s", e)
                self._pw_cm = None
            self._page = None
        self._ready = False

    def render_png(self, latex: str, *, display: bool = False) -> bytes | None:
        if not self._ready or self._page is None:
            return None

        latex_js = json.dumps(latex)
        display_js = "true" if display else "false"
        try:
            with _PLAYWRIGHT_LOCK:
                self._page.evaluate(
                    f"""
                    () => {{
                        katex.render({latex_js}, document.getElementById("formula"), {{
                            throwOnError: true,
                            displayMode: {display_js}
                        }});
                    }}
                    """
                )
                self._page.wait_for_selector("#formula .katex", state="attached", timeout=30_000)
                return self._page.locator("#formula").screenshot(type="png")
        except Exception as e:
            logger.warning("Playwright session render failed: %s", e, exc_info=False)
            return None


@contextmanager
def latex_render_batch():
    """Переиспользует один браузер для всех формул внутри блока."""
    session = _PlaywrightLatexSession()
    _BATCH_LOCAL.session = session
    try:
        yield
    finally:
        _BATCH_LOCAL.session = None
        session.stop()


def _ensure_batch_session(font_size_pt: float) -> _PlaywrightLatexSession | None:
    session = getattr(_BATCH_LOCAL, "session", None)
    if session is None:
        return None
    font_size_px = font_size_pt * _PX_PER_PT
    if session.start(font_size_px):
        return session
    return None


def _render_single_playwright(latex: str, *, font_size_pt: float, display: bool) -> bytes | None:
    session = _PlaywrightLatexSession()
    font_size_px = font_size_pt * _PX_PER_PT
    if not session.start(font_size_px):
        return None
    try:
        return session.render_png(latex, display=display)
    finally:
        session.stop()


@lru_cache(maxsize=512)
def _cached_playwright_png(latex_key: str, font_size_pt: float, display: bool) -> bytes:
    session = _ensure_batch_session(font_size_pt)
    if session is not None:
        png = session.render_png(latex_key, display=display)
    else:
        png = _render_single_playwright(latex_key, font_size_pt=font_size_pt, display=display)
    if not png:
        raise LookupError(latex_key)
    return png


def render_latex_to_png(
    latex: str,
    *,
    font_size_pt: float = 11.0,
    display: bool = False,
) -> bytes | None:
    """
    LaTeX → PNG через Playwright + KaTeX (CDN).
    font_size_pt и display должны совпадать с compute_formula_layout().
    """
    latex_key = (latex or "").strip()
    if not latex_key:
        return None

    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        logger.warning("playwright not installed")
        return _render_latex_matplotlib(latex_key, font_size_pt=font_size_pt)

    try:
        return _cached_playwright_png(latex_key, float(font_size_pt), bool(display))
    except LookupError:
        pass
    except Exception as e:
        logger.warning("render_latex_to_png failed: %s", e, exc_info=False)

    return _render_latex_matplotlib(latex_key, font_size_pt=font_size_pt)


def _render_latex_matplotlib(latex: str, *, font_size_pt: float) -> bytes | None:
    """Fallback, если Playwright/Chromium недоступны."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    expr = str(latex).strip()
    if not expr:
        return None

    fig_h = max(0.35, font_size_pt / 28.0)
    fig = plt.figure(figsize=(3.5, fig_h))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    try:
        ax.text(
            0.5,
            0.5,
            f"${expr}$",
            fontsize=max(10, font_size_pt),
            ha="center",
            va="center",
        )
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=160, bbox_inches="tight", pad_inches=0.02, transparent=True)
        return buf.getvalue() or None
    except Exception as e:
        logger.warning("_render_latex_matplotlib failed: %s", e, exc_info=False)
        return None
    finally:
        plt.close(fig)
