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

# Todos os possíveis botões de fechar cookie banner
COOKIE_SELECTORS = [
    'button:has-text("Accept All Cookies")',
    'button:has-text("Allow All")',
    'button:has-text("Confirm My Choices")',
    'button:has-text("Aceitar todos")',
    'button:has-text("Aceitar")',
    '#onetrust-accept-btn-handler',
    '.onetrust-accept-btn-handler',
    '.save-preference-btn-handler',
]


def _dismiss_cookies(page, wait_seconds: int = 4):
    """Aguarda e fecha qualquer banner de cookies."""
    time.sleep(wait_seconds)
    dismissed = False
    for selector in COOKIE_SELECTORS:
        try:
            el = page.locator(selector).first
            if el.is_visible(timeout=2_000):
                el.click(timeout=3_000)
                logger.info(f"Cookie banner fechado: {selector}")
                time.sleep(1.5)
                dismissed = True
                break
        except Exception:
            continue

    # Tenta uma segunda vez caso tenha múltiplos banners
    if dismissed:
        for selector in COOKIE_SELECTORS:
            try:
                el = page.locator(selector).first
                if el.is_visible(timeout=1_500):
                    el.click(timeout=3_000)
                    logger.info(f"Cookie banner secundário fechado: {selector}")
                    time.sleep(1)
                    break
            except Exception:
                continue
    else:
        logger.info("Nenhum banner de cookies encontrado.")


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
        page = context.new_page()

        try:
            # ── 1. Login ──────────────────────────────────────────────────────
            logger.info("Abrindo página de login...")
            page.goto(
                f"https://{PIPEDRIVE_DOMAIN}.pipedrive.com/auth/login",
                wait_until="domcontentloaded",
                timeout=30_000,
            )

            _dismiss_cookies(page, wait_seconds=3)

            page.locator('input[name="login"], input[type="email"]').first.fill(PIPEDRIVE_EMAIL)
            time.sleep(0.5)
            page.locator('input[name="password"], input[type="password"]').first.fill(PIPEDRIVE_PASSWORD)
            time.sleep(0.5)

            submitted = False
            for selector in [
                'button[type="submit"]',
                'button:has-text("Log in")',
                'button:has-text("Entrar")',
                'button:has-text("Sign in")',
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

            # ── 2. Navegar direto para o filtro ───────────────────────────────
            logger.info("Navegando para o filtro...")
            try:
                page.goto(PIPEDRIVE_FILTER_URL, wait_until="commit", timeout=30_000)
            except Exception:
                pass

            # Aguarda SPA carregar + fecha cookie banner com espera longa
            _dismiss_cookies(page, wait_seconds=6)
            logger.info("Página com filtro carregada e cookies dispensados.")

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
                '[class*="header"] button:last-child',
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
                page.screenshot(path=str(DOWNLOAD_DIR / "debug_before_menu.png"))
                buttons = page.locator("button").all()
                logger.info(f"Botões na página ({len(buttons)}):")
                for i, btn in enumerate(buttons[:30]):
                    try:
                        txt  = btn.inner_text().strip()
                        aria = btn.get_attribute("aria-label") or ""
                        dt   = btn.get_attribute("data-test") or ""
                        cls  = (btn.get_attribute("class") or "")[:60]
                        logger.info(f"  [{i}] texto='{txt}' aria='{aria}' data-test='{dt}' class='{cls}'")
                    except Exception:
                        pass
                raise Exception("Não foi possível abrir o menu de três pontos.")

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
