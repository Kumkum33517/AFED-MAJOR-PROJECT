"""Browser smoke test: every role signs in through the real form and opens every page it can reach.

Fails on an uncaught error or a console error, on a page that does not render its heading, and on a page a
role can open that it should not. Needs the API and the frontend running on demo data (scripts/seed.py).

    pip install -r e2e/requirements.txt && playwright install chromium
    python e2e/smoke.py --url http://localhost:5173
"""
import argparse
import sys

from playwright.sync_api import Page, sync_playwright

PASSWORD = "afed1234"  # the local demo password, never a real one
EVERYONE = ["/dashboard", "/alerts", "/cases", "/entities", "/evaluation", "/reports", "/notifications", "/profile"]
ROLES = {  # role: (pages it may open, pages it must be refused, page it lands on)
    "admin": (EVERYONE + ["/upload", "/settings", "/users"], [], "/dashboard"),
    "analyst": (EVERYONE + ["/upload", "/settings"], ["/users"], "/upload"),
    "reviewer": (EVERYONE, ["/upload", "/settings", "/users"], "/alerts"),
    "viewer": (EVERYONE, ["/upload", "/settings", "/users"], "/dashboard"),
}
REFUSED = "This page is not available to your role"


def sign_in(page: Page, url: str, role: str) -> None:
    page.goto(f"{url}/login")
    page.get_by_label("Email").fill(f"{role}@afed.app")
    page.get_by_label("Password").fill(PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_url(lambda u: "/login" not in u)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:5173")
    parser.add_argument("--browser-channel", default=None, help='e.g. "chrome" to use an installed Chrome')
    args = parser.parse_args()
    failures: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=args.browser_channel)
        page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
        problems: list[str] = []
        page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
        page.on("console", lambda m: problems.append(f"console: {m.text}") if m.type == "error" else None)

        page.goto(args.url)
        if page.get_by_role("link", name="Open dashboard").count() != 1:
            failures.append("landing: no Open dashboard link")

        for role, (allowed, refused, home) in ROLES.items():
            page.context.clear_cookies()
            page.evaluate("localStorage.clear()")
            sign_in(page, args.url, role)
            if not page.url.endswith(home):
                failures.append(f"{role}: landed on {page.url}, expected {home}")
            for path in allowed:
                problems.clear()
                page.goto(f"{args.url}{path}")
                page.wait_for_load_state("networkidle")
                if page.locator("h1").count() == 0 or page.get_by_text(REFUSED).count():
                    failures.append(f"{role} {path}: no heading, or refused")
                failures += [f"{role} {path}: {p}" for p in problems]
            for path in refused:
                page.goto(f"{args.url}{path}")
                page.wait_for_load_state("networkidle")
                if page.get_by_text(REFUSED).count() == 0:
                    failures.append(f"{role} {path}: should be refused")
            print(f"ok   {role}: {len(allowed)} pages open, {len(refused)} refused", flush=True)

        # The sample file goes through the real preview and mapping, as a judge would see it.
        page.goto(f"{args.url}/upload")
        page.evaluate("localStorage.clear()")
        sign_in(page, args.url, "analyst")
        page.get_by_role("button", name="Use the NSPCL sample").click()
        page.get_by_text("2. Map the columns").wait_for(timeout=30_000)
        page.get_by_role("button", name="Validate").click()
        page.get_by_text("5,745 rows read").wait_for(timeout=30_000)
        print("ok   sample upload: preview, mapping and validation", flush=True)
        browser.close()

    if failures:
        print("\n".join(f"FAIL {f}" for f in failures))
        sys.exit(1)
    print("all browser checks passed")


if __name__ == "__main__":
    main()
