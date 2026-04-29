import os
import time
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

DOWNLOAD_DIR = Path("/app/downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

PIPEDRIVE_EMAIL    = os.environ["PIPEDRIVE_EMAIL"]
PIPEDRIVE_PASSWORD = os.environ["PIPEDRIVE_PASSWORD"]
PIPEDRIVE_DOMAIN   = os.environ.get("PIPEDRIVE_DOMAIN", "webcontinental")
FILTER_NAME        = os.environ.get("PIPEDRIVE_FILTER", "[GALLANT] Leads criados - diários.")


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
            page.goto(f"https://{PIPEDRIVE_DOMAIN}.pipedrive.com/auth/login", wait_until="domcontentloaded")
            time.sleep(3)

            # Preenche email
            page.locator('input[name="login"], input[type="email"]').first.fill(PIPEDRIVE_EMAIL)
            time.sleep(0.5)

            # Preenche senha
            page.locator('input[name="password"], input[type="password"]').first.fill(PIPEDRIVE_PASSWORD)
            time.sleep(0.5)

            # Tenta clicar no botão de submit
            try:
                page.locator('button[type="submit"]').click(timeout=5_000)
            except PlaywrightTimeout:
                try:
                    page.locator('button:has-text("Log in"), button:has-text("Entrar"), button:has-text("Sign in")').first.click(timeout=5_000)
                except PlaywrightTimeout:
                    page.locator('input[type="password"]').first.press("Enter")

            # Aguarda redirecionamento pós-login
            page.wait_for_url(f"**/{PIPEDRIVE_DOMAIN}.pipedrive.com/**", timeout=30_000)
            logger.info("Login efetuado com sucesso.")

            # ── 2. Ir para Negócios ───────────────────────────────────────────
            page.goto(f"https://{PIPEDRIVE_DOMAIN}.pipedrive.com/deals", wait_until="networkidle")
            logger.info("Página de Negócios carregada.")

            # ── 3. Aplicar filtro ─────────────────────────────────────────────
            _apply_filter(page, FILTER_NAME)

            # ── 4. Exportar CSV ───────────────────────────────────────────────
            downloaded_file = _export_csv(page)

            logger.info(f"Arquivo exportado: {downloaded_file}")
            return downloaded_file

        except Exception as exc:
            screenshot = DOWNLOAD_DIR / "error_screenshot.png"
            page.screenshot(path=str(screenshot))
            logger.error(f"Erro durante o RPA: {exc}. Screenshot salvo em {screenshot}")
            raise
        finally:
            context.close()
            browser.close()


def _apply_filter(page, filter_name: str):
    logger.info(f"Aplicando filtro: {filter_name}")
    try:
        page.locator('[data-test="filter-button"], [aria-label*="filtro"], [aria-label*="filter"]').first.click(timeout=10_000)
    except PlaywrightTimeout:
        page.locator('button:has-text("Filtro"), button:has-text("Filter")').first.click()

    time.sleep(1)
    filter_item = page.locator(f'text="{filter_name}"').first
    filter_item.wait_for(timeout=15_000)
    filter_item.click()
    page.wait_for_load_state("networkidle")
    logger.info("Filtro aplicado.")


def _export_csv(page) -> Path:
    logger.info("Iniciando exportação CSV...")
    try:
        page.locator('[data-test="more-options"], button[aria-label*="ações"], button[aria-label*="mais"]').first.click(timeout=8_000)
    except PlaywrightTimeout:
        page.locator('button:has-text("Exportar"), button:has-text("Export")').first.click()

    time.sleep(0.8)

    with page.expect_download(timeout=60_000) as download_info:
        try:
            page.locator('text="Exportar dados", text="Export data", text="Exportar CSV"').first.click()
        except Exception:
            page.locator('[data-test="export-button"]').click()

    download = download_info.value
    dest = DOWNLOAD_DIR / download.suggested_filename
    download.save_as(str(dest))
    logger.info(f"Download concluído: {dest}")
    return dest
