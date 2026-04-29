import os
import time
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

DOWNLOAD_DIR = Path("/app/downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

PIPEDRIVE_EMAIL      = os.environ["PIPEDRIVE_EMAIL"]
PIPEDRIVE_PASSWORD   = os.environ["PIPEDRIVE_PASSWORD"]
PIPEDRIVE_DOMAIN     = os.environ.get("PIPEDRIVE_DOMAIN", "webcontinentalb2b")
PIPEDRIVE_FILTER_URL = os.environ.get(
    "PIPEDRIVE_FILTER_URL",
    "https://webcontinentalb2b.pipedrive.com/deals/pipeline/1/filter/358?quickFilter=none"
)

# Cookies do OneTrust que indicam "usuário já aceitou" — evita o banner
ONETRUST_COOKIES = [
    {
        "name": "OptanonAlertBoxClosed",
        "value": "2024-01-01T00:00:00.000Z",
        "domain": ".pipedrive.com",
        "path": "/",
    },
    {
        "name": "OptanonConsent",
        "value": "isGpcEnabled=0&datestamp=Mon+Jan+01+2024+00%3A00%3A00+GMT&version=202301.1.0&isIABGlobal=false&hosts=&landingPath=NotLandingPage&groups=C0001%3A1%2CC0002%3A1%2CC0003%3A1%2CC0004%3A1&AwaitingReconsent=false",
        "domain": ".pipedrive.com",
        "path": "/",
    },
]

COOKIE_JS = """
() => {
    const texts = ['Allow All', 'Accept All Cookies', 'Confirm My Choices', 'Aceitar todos'];
    const allButtons = Array.from(document.querySelectorAll('button'));
    for (const text of texts) {
        const btn = allButtons.find(b => b.textContent.trim().includes(text));
        if (btn) { btn.click(); return 'clicked: ' + text; }
    }
    return null;
}
"""


def _inject_onetrust_cookies(context):
    """Injeta cookies que simulam aceitação prévia do OneTrust."""
    context.add_cookies(ONETRUST_COOKIES)
    logger.info("Cookies OneTrust injetados.")


def _dismiss_cookies_js(page):
    """Fallback: fecha banner via JS caso ainda apareça."""
    try:
        result = page.evaluate(COOKIE_JS)
        if result:
            logger.info(f"Banner fechado via JS: {result}")
            time.sleep(1.5)
    except Exception:
        pass


def run() -> Path:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            accept_downloads=True,
            viewport={"width": 1280, "height": 900},
        )

        # Injeta cookies ANTES de qualquer navegação
        _inject_onetrust_cookies(context)

        page = context.new_page()

        try:
            # ── 1. Login ──────────────────────────────────────────────────────
            logger.info("Abrindo página de login...")
            page.goto(
                f"https://{PIPEDRIVE_DOMAIN}.pipedrive.com/auth/login",
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            time.sleep(2)
            _dismiss_cookies_js(page)  # fallback

            page.locator('input[name="login"], input[type="email"]').first.fill(PIPEDRIVE_EMAIL)
            time.sleep(0.5)
            page.locator('input[name="password"], input[type="password"]').first.fill(PIPEDRIVE_PASSWORD)
            time.sleep(0.5)

            submitted = False
            for selector in [
                'button[type="submit"]',
                'button:has-text("Log in")',
                'button:has-text("Entrar")',
            ]:
                try:
                    page.locator(selector).first.click(timeout=4_000)
                    submitted = True
                    break
                except PlaywrightTimeout:
                    continue
            if not submitted:
                page.locator('input[type="password"]').first.press("Enter")

            page.wait_for_url(f"**/{PIPEDRIVE_DOMAIN}.pipedrive.com/**", timeout=30_000)
            logger.info("Login efetuado com sucesso.")

            # Re-injeta cookies após login (sessão nova)
            _inject_onetrust_cookies(context)

            # ── 2. Navegar direto para o filtro ───────────────────────────────
            logger.info("Navegando para o filtro...")
            try:
                page.goto(PIPEDRIVE_FILTER_URL, wait_until="commit", timeout=30_000)
            except Exception:
                pass

            time.sleep(7)
            _dismiss_cookies_js(page)  # fallback
            time.sleep(2)

            page.screenshot(path=str(DOWNLOAD_DIR / "debug_after_filter.png"))
            logger.info("Screenshot de debug salvo.")

            # Loga botões para confirmar que é a página certa
            buttons = page.locator("button").all()
            logger.info(f"Botões na página ({len(buttons)}):")
            for i, btn in enumerate(buttons[:20]):
                try:
                    txt  = btn.inner_text().strip()
                    aria = btn.get_attribute("aria-label") or ""
                    dt   = btn.get_attribute("data-test") or ""
                    logger.info(f"  [{i}] texto='{txt}' aria='{aria}' data-test='{dt}'")
                except Exception:
                    pass

            # ── 3. Clicar no botão "..." (três pontos) ────────────────────────
            logger.info("Abrindo menu de três pontos...")
            three_dots_clicked = False
            for selector in [
                'button[data-test="toolbar-kebab-menu"]',
                'button[aria-label="Mais opções"]',
                'button[aria-label="More options"]',
                '[data-test="kebab-menu"]',
                'button[class*="kebab"]',
                'button:has(svg[data-icon="ellipsis"])',
                '[class*="toolbar"] button:last-child',
                '[class*="list-header"] button:last-child',
            ]:
                try:
                    el = page.locator(selector).last
                    if el.is_visible(timeout=3_000):
                        el.click(timeout=5_000)
                        three_dots_clicked = True
                        logger.info(f"Menu aberto com seletor: {selector}")
                        break
                except Exception:
                    continue

            if not three_dots_clicked:
                raise Exception(
                    "Não foi possível abrir o menu de três pontos. "
                    "Verifique debug_after_filter.png e os botões logados acima."
                )

            time.sleep(1)

            # ── 4. Clicar em "Exportar resultados do filtro" ──────────────────
            logger.info("Clicando em Exportar resultados do filtro...")
            with page.expect_download(timeout=60_000) as download_info:
                export_clicked = False
                for selector in [
                    'text="Exportar resultados do filtro"',
                    'text="Export filter results"',
                    'text="Exportar resultados"',
                    'text="Exportar dados"',
                    'text="Export data"',
                    '[data-test="export-button"]',
                    'button:has-text("Exportar")',
                ]:
                    try:
                        page.locator(selector).first.click(timeout=5_000)
                        export_clicked = True
                        logger.info(f"Exportar clicado: {selector}")
                        break
                    except PlaywrightTimeout:
                        continue

                if not export_clicked:
                    raise Exception("Não foi possível encontrar o botão de exportar.")

            download = download_info.value
            dest = DOWNLOAD_DIR / download.suggested_filename
            download.save_as(str(dest))
            logger.info(f"✅ Download concluído: {dest}")
            return dest

        except Exception as exc:
            try:
                page.screenshot(path=str(DOWNLOAD_DIR / "error_screenshot.png"))
                logger.error("Screenshot de erro salvo.")
            except Exception:
                pass
            logger.error(f"Erro durante o RPA: {exc}")
            raise
        finally:
            context.close()
            browser.close()
