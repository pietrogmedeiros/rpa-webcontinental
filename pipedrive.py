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
PIPEDRIVE_DOMAIN   = os.environ.get("PIPEDRIVE_DOMAIN", "webcontinentalb2b")
PIPEDRIVE_FILTER_URL = os.environ.get(
    "PIPEDRIVE_FILTER_URL",
    f"https://{os.environ.get('PIPEDRIVE_DOMAIN', 'webcontinentalb2b')}.pipedrive.com/deals/pipeline/1/filter/358?quickFilter=none"
)


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
            logger.info(f"Navegando para o filtro: {PIPEDRIVE_FILTER_URL}")
            try:
                page.goto(PIPEDRIVE_FILTER_URL, wait_until="commit", timeout=30_000)
            except Exception:
                pass  # SPA aborta mas continua carregando

            time.sleep(6)
            logger.info("Página com filtro carregada.")

            # ── 3. Clicar no botão "..." (três pontos) ────────────────────────
            logger.info("Abrindo menu de três pontos...")
            three_dots_clicked = False
            for selector in [
                'button[data-test="toolbar-kebab-menu"]',
                'button[aria-label="Mais opções"]',
                'button[aria-label="More options"]',
                '[data-test="kebab-menu"]',
                'button:has-text("...")',
                # botão com ícone de 3 pontos no canto superior direito
                'button[class*="kebab"]',
                'button[class*="more"]',
                'button[class*="dots"]',
            ]:
                try:
                    el = page.locator(selector).last  # pega o último (canto direito)
                    if el.is_visible(timeout=3_000):
                        el.click(timeout=5_000)
                        three_dots_clicked = True
                        logger.info(f"Menu aberto com seletor: {selector}")
                        break
                except Exception:
                    continue

            if not three_dots_clicked:
                # Fallback: tira screenshot para debug e loga os botões
                page.screenshot(path=str(DOWNLOAD_DIR / "debug_before_menu.png"), full_page=False)
                buttons = page.locator("button").all()
                logger.info(f"Botões na página ({len(buttons)}):")
                for i, btn in enumerate(buttons[:30]):
                    try:
                        txt = btn.inner_text().strip()
                        aria = btn.get_attribute("aria-label") or ""
                        dt = btn.get_attribute("data-test") or ""
                        cls = btn.get_attribute("class") or ""
                        logger.info(f"  [{i}] texto='{txt}' aria='{aria}' data-test='{dt}' class='{cls[:50]}'")
                    except Exception:
                        pass
                raise Exception("Não foi possível abrir o menu de três pontos. Veja debug_before_menu.png")

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
                ]:
                    try:
                        page.locator(selector).first.click(timeout=5_000)
                        export_clicked = True
                        logger.info(f"Exportar clicado com seletor: {selector}")
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
