# Inspeção reutilizável de formulários web.

from __future__ import annotations

import asyncio

from app.browser.browser_manager import BrowserManager
from app.browser.form_detector import FormDetector
from app.browser.page_inspector import PageInspector, validate_url
from app.config import Settings, get_settings
from app.schemas.form import DetectionResult


# Executa a navegação e a detecção de campos de uma URL.
class InspectionService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def inspect(self, url: str) -> DetectionResult:
        safe_url = validate_url(url)

        async with BrowserManager(self.settings) as manager:
            page = await manager.new_page()
            inspector = PageInspector()
            snapshot = await inspector.navigate(page, safe_url)
            detector = FormDetector()
            return await detector.detect(page, snapshot)

    # Versão síncrona usada pela CLI e por workers em thread.
    def inspect_sync(self, url: str) -> DetectionResult:
        return asyncio.run(self.inspect(url))
