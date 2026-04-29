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
            page.goto(
                f"https://{PIPEDRIVE_DOMAIN}.pipedrive.com/auth/login",
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            time.sleep(3)

            page.locator('input[name="login"], input[type="email"]').first.fill(PIPEDRIVE_EMAIL)
            time.sleep(0.5)
            page.locator('input[name="password"], input[type="password"]').first.fill(PIPEDRIVE_PASSWORD)
            time.sleep(0.5)

            # Tenta clicar no botão — fallback para Enter
            submitted = False
            for selector in ['button[type="submit"]', 'button:has-text("Log in")', 'button:has-text("Entrar")']:
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

            # ── 2. Ir para Negócios ───────────────────────────────────────────
            logger.info("Navegando para Negócios...")
            page.goto(
                f"https://{PIPEDRIVE_DOMAIN}.pipedrive.com/deals",
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            time.sleep(5)  # aguarda JS da SPA carregar
            logger.info("Página de Negócios carregada.")

            # ── 3. Aplicar filtro ─────────────────────────────────────────────
            _apply_filter(page, FILTER_NAME)

            # ── 4. Exportar CSV ───────────────────────────────────────────────
            downloaded_file = _export_csv(page)

            logger.info(f"Arquivo exportado: {downloaded_file}")
            return downloaded_file

        except Exception as exc:
            screenshot = DOWNLOAD_DIR / "error_screenshot.png"
            try:
                page.screenshot(path=str(screenshot))
                logger.error(f"Screenshot salvo em {screenshot}")
            except Exception:
                pass
            logger.error(f"Erro durante o RPA: {exc}")
            raise
        finally:
            context.close()
            browser.close()


def _apply_filter(page, filter_name: str):
    logger.info(f"Aplicando filtro: {filter_name}")

    # Tenta abrir o seletor de filtros
    filter_opened = False
    for selector in [
        '[data-test="filter-button"]',
        '[aria-label*="filtro"]',
        '[aria-label*="filter"]',
        'button:has-text("Filtro")',
        'button:has-text("Filter")',
    ]:
        try:
            page.locator(selector).first.click(timeout=5_000)
            filter_opened = True
            break
        except PlaywrightTimeout:
            continue

    if not filter_opened:
        raise Exception("Não foi possível abrir o seletor de filtros.")

    time.sleep(1.5)

    # Clica no filtro pelo nome
    try:
        page.locator(f'text="{filter_name}"').first.click(timeout=10_000)
    except PlaywrightTimeout:
        # Tenta sem aspas (match parcial)
        page.locator(f'text={filter_name}').first.click(timeout=10_000)

    time.sleep(3)
    logger.info("Filtro aplicado.")


def _export_csv(page) -> Path:
    logger.info("Iniciando exportação CSV...")

    # Abre menu de mais opções
    menu_opened = False
    for selector in [
        '[data-test="more-options"]',
        'button[aria-label*="ações"]',
        'button[aria-label*="mais"]',
        'button[aria-label*="more"]',
        '[data-icon="kebab-menu"]',
        'button:has-text("...")',
    ]:
        try:
            page.locator(selector).first.click(timeout=4_000)
            menu_opened = True
            break
        except PlaywrightTimeout:
            continue

    time.sleep(1)

    # Clica em exportar
    with page.expect_download(timeout=60_000) as download_info:
        export_clicked = False
        for selector in [
            'text="Exportar dados"',
            'text="Export data"',
            'text="Exportar CSV"',
            'text="Export CSV"',
            '[data-test="export-button"]',
            'button:has-text("Exportar")',
        ]:
            try:
                page.locator(selector).first.click(timeout=4_000)
                export_clicked = True
                break
            except PlaywrightTimeout:
                continue

        if not export_clicked:
            raise Exception("Não foi possível encontrar o botão de exportar.")

    download = download_info.value
    dest = DOWNLOAD_DIR / download.suggested_filename
    download.save_as(str(dest))
    logger.info(f"Download concluído: {dest}")
    return dest
