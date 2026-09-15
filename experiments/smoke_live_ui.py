"""Optional isolated Playwright test; never opens or reuses a personal profile."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def run(url, output, executable=None):
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        options = {"headless": True}
        if executable:
            options["executable_path"] = executable
        browser = playwright.chromium.launch(**options)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1100}, device_scale_factor=1
        )
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url)
        expect(page.locator("#answer")).to_contain_text("Недостаточно оснований")
        page.get_by_role("button", name="1 Запомнить исходный факт", exact=False).click()
        expect(page.locator("#answer")).to_contain_text("30 s")
        page.get_by_role("button", name="2 Добавить другую версию", exact=False).click()
        expect(page.locator("#answer")).to_contain_text("Нельзя выбрать одно значение")
        page.locator(".fact-node").filter(has_text="60 s").click()
        expect(page.locator("#inspector")).to_contain_text("scenario://checkout/release-v1")
        page.screenshot(path=str(output / "live-conflict.png"), full_page=True)
        page.get_by_role("button", name="3 Подтвердить замену", exact=False).click()
        expect(page.locator("#answer")).to_contain_text("Поддерживается памятью")
        expect(page.locator("#answer .answer-value")).to_have_text("60 s")
        page.screenshot(path=str(output / "live-resolved.png"), full_page=True)
        page.locator("#known-at").focus()
        page.locator("#known-at").press("ArrowLeft")
        expect(page.locator("#answer")).to_contain_text("Нельзя выбрать одно значение")
        page.locator("#valid-at").focus()
        page.locator("#valid-at").press("Home")
        expect(page.locator("#answer .answer-value")).to_have_text("30 s")
        page.reload()
        expect(page.locator("#answer .answer-value")).to_have_text("60 s")
        page.get_by_text("＋ Добавить утверждение", exact=True).click()
        form = page.locator("#fact-form")
        form.locator('[name="environment"]').fill("staging")
        form.locator('[name="excerpt"]').fill('<script>alert("not executable")</script>')
        form.get_by_role("button", name="Записать в память", exact=True).click()
        expect(page.locator("#answer .answer-value")).to_have_text("90 s")
        page.locator(".fact-node").filter(has_text="90 s").click()
        expect(page.locator("#inspector .evidence")).to_have_text(
            '<script>alert("not executable")</script>'
        )
        page.locator("#query-environment").fill("production")
        page.get_by_role("button", name="Спросить", exact=False).click()
        expect(page.locator("#answer .answer-value")).to_have_text("60 s")
        with page.expect_download() as download:
            page.get_by_role("button", name="Экспорт объяснения", exact=False).click()
        downloaded = output / "live-trace.json"
        download.value.save_as(str(downloaded))
        payload = json.loads(downloaded.read_text(encoding="utf-8"))
        assert payload["model_calls"] == 0 and len(payload["facts"]) == 3
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(output / "live-mobile.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        assert not errors, errors
        page.get_by_role("button", name="Новая сессия", exact=False).click()
        expect(page.locator("#answer")).to_contain_text("Недостаточно оснований")
        assert page.locator(".fact-node").count() == 0
        context.close()
        browser.close()
        print(
            "PASS: writes, conflict, resolution, both time axes, reload, scope, "
            "XSS escaping, export, mobile, new workspace"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8766/")
    parser.add_argument("--output", type=Path, default=Path("outputs/ui"))
    parser.add_argument("--executable", default=None)
    args = parser.parse_args()
    run(args.url, args.output, args.executable)
