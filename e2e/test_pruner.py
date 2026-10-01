"""Acceptance suite for the Dashboard Pruner app (Playwright, stdlib + playwright).

Run seed.py first. Environment:
    DHIS2_URL      instance base URL (API calls and, in installed mode, the app)
    APP_MODE       "installed" (default) or "dev"
    APP_KEY        installed app key (installed mode, default Dashboard-Pruner-Tool)
    APP_URL        dev server URL (dev mode)
    DEV_SERVER     server URL to type into the dev shell login (dev mode)
    RESULTS_DIR    where results.json and screenshots go (default e2e/results)
"""
import json
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

import dhis2api as api

APP_MODE = os.environ.get("APP_MODE", "installed")
APP_KEY = os.environ.get("APP_KEY", "Dashboard-Pruner-Tool")
APP_URL = os.environ.get("APP_URL", "http://localhost:3000")
DEV_SERVER = os.environ.get("DEV_SERVER", "http://localhost:8080")
HERE = os.path.dirname(__file__)
RESULTS_DIR = os.environ.get("RESULTS_DIR", os.path.join(HERE, "results"))

CHECK_NO_ITEMS = "dashboards_no_items"
CHECK_NOT_VIEWED = "dashboards_not_viewed_one_year"

SEL_CHECK_SELECT = "[data-test='check-select']"
SEL_SELECT_INPUT = "[data-test='dhis2-uicore-select-input']"
SEL_TABLE = "[data-test='dashboard-table']"
SEL_ROW = "[data-test='dashboard-row']"
SEL_EMPTY = "[data-test='empty-state']"
SEL_SEARCH = "[data-test='search'] input"
SEL_PAGINATION = "[data-test='dhis2-uiwidgets-pagination-summary']"
SEL_ALERT = "[data-test='dhis2-uicore-alertbar']"
SEL_SELECT_ALL = "[data-test='select-all'] input"
SEL_DELETE_SELECTED = "[data-test='delete-selected']"
SEL_DELETE_ROW = "[data-test='delete-row']"
SEL_CONFIRM = "[data-test='confirm-delete']"
SEL_MODAL = "[data-test='delete-modal']"
SEL_HEADERS = f"{SEL_TABLE} thead th"
SEL_REFRESHING = "[role='status']"
SEL_SELECT_ROW = "[data-test='select-row'] input"
SEARCH_PRIVATE = "PRUNER-TEST private"
CHECK_TIMEOUT_MS = int(os.environ.get("CHECK_TIMEOUT_MS", "180000"))
# Platform noise that is not caused by the app (see UI-TEST-RESULTS.md)
IGNORED_ERRORS = ("not a secure context", "logo_banner", "Failed to load resource")
# Up to 2.41 the app looks up dashboards by id; 404 means "deleted since the
# check ran" and is handled
EXPECTED_404 = re.compile(r"^404 .*/api/\d+/dashboards/[A-Za-z0-9]{11}\?fields=")

with open(os.path.join(HERE, "seed-state.json")) as handle:
    STATE = json.load(handle)
SEEDED = STATE["dashboards"]
USERS = STATE["users"]


class Session:
    """One logged-in browser context with captured event streams."""

    def __init__(self, browser, user, password):
        self.context = browser.new_context(viewport={"width": 1400, "height": 1000})
        self.events = {"console_errors": [], "page_errors": [], "http_errors": []}
        self.integrity_posts = 0
        self.page = self.context.new_page()
        self.page.on("console", self._on_console)
        self.page.on("pageerror", lambda e: self.events["page_errors"].append(str(e)))
        self.page.on("response", self._on_response)
        self.page.on("request", self._on_request)
        self.root = self._open(user, password)

    def _on_console(self, msg):
        if msg.type == "error":
            self.events["console_errors"].append(msg.text)

    def _on_request(self, req):
        if req.method == "POST" and "/dataIntegrity" in req.url:
            self.integrity_posts += 1

    def unexpected_errors(self):
        errors = self.events["page_errors"] + self.events["console_errors"]
        errors += self.events["http_errors"]
        return [
            e for e in errors
            if not any(n in e for n in IGNORED_ERRORS) and not EXPECTED_404.match(e)
        ]

    def _on_response(self, resp):
        if resp.status >= 400:
            self.events["http_errors"].append(f"{resp.status} {resp.url}")

    def _open(self, user, password):
        if APP_MODE == "dev":
            self.page.goto(APP_URL)
            self.page.get_by_text("Please sign in").wait_for(timeout=60000)
            inputs = self.page.locator("input")
            inputs.nth(0).fill(DEV_SERVER)
            inputs.nth(1).fill(user)
            inputs.nth(2).fill(password)
            self.page.get_by_role("button", name="Sign in").click()
        else:
            name, value = api.session_cookie(user, password)
            host = re.sub(r"^https?://", "", api.BASE_URL).split(":")[0]
            self.context.add_cookies([{"name": name, "value": value, "domain": host, "path": "/"}])
            self.page.goto(f"{api.BASE_URL}/api/apps/{APP_KEY}/index.html")
        return self._find_app_frame()

    def _find_app_frame(self, timeout_s=90):
        # 2.42+ wraps installed apps in the global-shell iframe
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            for frame in self.page.frames:
                try:
                    if frame.locator("h1", has_text="Dashboard pruner").count():
                        return frame
                except Exception:  # frame detached while navigating
                    continue
            time.sleep(0.5)
        raise TimeoutError("App did not render")

    def goto_check(self, code):
        # The selected check lives in the hash route (?check=...)
        self.root.evaluate(f"() => {{ window.location.hash = '#/?check={code}' }}")
        self.wait_for_check(code)

    def wait_for_check(self, code):
        # Only the not-viewed table has a "Last viewed" column; wait for the
        # table of this check before waiting for its results
        last_viewed = self.root.locator(SEL_HEADERS, has_text="Last viewed")
        deadline = time.time() + CHECK_TIMEOUT_MS / 1000
        while time.time() < deadline:
            table = self.root.locator(SEL_TABLE).count() > 0
            if table and (last_viewed.count() > 0) == (code == CHECK_NOT_VIEWED):
                break
            time.sleep(0.25)
        self.wait_for_results()

    def wait_for_results(self):
        # Rows may first show a cached result while the check reruns
        self.root.locator(f"{SEL_ROW}, {SEL_EMPTY}").first.wait_for(timeout=CHECK_TIMEOUT_MS)
        self.root.locator(SEL_REFRESHING).wait_for(state="detached", timeout=CHECK_TIMEOUT_MS)

    def total(self):
        """Row count from the pagination footer (table is client-side paginated)."""
        if self.root.locator(SEL_EMPTY).count():
            return 0
        text = self.root.locator(SEL_PAGINATION).inner_text()
        return int(re.search(r"of (\d+)\s*$", text.strip()).group(1))

    def search(self, term):
        # Filtering is synchronous client-side; wait until the input holds it
        field = self.root.locator(SEL_SEARCH)
        field.fill(term)
        self.root.wait_for_function(
            "([sel, v]) => document.querySelector(sel)?.value === v",
            arg=[SEL_SEARCH, term],
        )

    def headers(self):
        return [h.strip() for h in self.root.locator(SEL_HEADERS).all_inner_texts()]

    def wait_alerts_gone(self):
        # Alerts auto-hide; a lingering one would be mistaken for the next result
        alerts = self.root.locator(SEL_ALERT)
        for i in range(alerts.count()):
            alerts.nth(i).wait_for(state="detached", timeout=30000)

    def alert_text(self):
        alert = self.root.locator(SEL_ALERT).last
        alert.wait_for(timeout=120000)
        return alert.inner_text()

    def shot(self, name):
        self.page.screenshot(path=os.path.join(RESULTS_DIR, f"{name}.png"), full_page=True)

    def close(self):
        self.context.close()


def flow_default_check(s):
    s.wait_for_results()
    expected = len(api.run_check(CHECK_NO_ITEMS))
    s.search("")
    shown = s.total()
    s.shot("01-no-items")
    assert shown == expected, f"table shows {shown}, API reports {expected}"
    assert not any("Last viewed" in h for h in s.headers()), s.headers()
    return f"{shown} empty dashboards listed (API: {expected})"


def flow_not_viewed_check(s):
    s.root.locator(SEL_CHECK_SELECT).locator(SEL_SELECT_INPUT).click()
    s.root.get_by_text("Dashboards not viewed in one year").last.click()
    s.wait_for_check(CHECK_NOT_VIEWED)
    expected = len(api.run_check(CHECK_NOT_VIEWED))
    shown = s.total()
    s.shot("02-not-viewed")
    assert shown == expected, f"table shows {shown}, API reports {expected}"
    assert any("Last viewed" in h for h in s.headers()), s.headers()
    return f"{shown} stale dashboards listed (API: {expected}); Last viewed column shown"


def flow_search_and_labels(s):
    s.goto_check(CHECK_NO_ITEMS)
    s.search(SEARCH_PRIVATE)
    private = s.total()
    s.search("PRUNER-TEST public-view")
    label = s.root.locator(SEL_ROW).first.inner_text()
    s.search("")
    assert private == 4, f"expected 4 private test dashboards, got {private}"
    assert "Public (can view)" in label, label
    return "search narrows to 4 rows; public read-only shown as 'Public (can view)'"


def flow_open_link(s):
    s.search("PRUNER-TEST shared-edit")
    href = s.root.locator(f"{SEL_ROW} a").first.get_attribute("href")
    resp = s.context.request.get(href)
    s.search("")
    assert href.endswith(f"#/{SEEDED['shared-edit']}"), href
    assert resp.ok, f"{resp.status} for {href}"
    return f"link {href} -> HTTP {resp.status}"


def flow_single_delete(s):
    uid = SEEDED["private-1"]
    s.goto_check(CHECK_NO_ITEMS)
    s.search("PRUNER-TEST private-1")
    s.root.locator(SEL_DELETE_ROW).first.click()
    s.root.locator(SEL_MODAL).wait_for()
    s.shot("03-confirm-single")
    s.wait_alerts_gone()
    s.root.locator(SEL_CONFIRM).click()
    alert = s.alert_text()
    s.wait_for_results()
    kept_search = s.root.locator(SEL_SEARCH).input_value()
    remaining = s.total()
    s.search("")
    assert "1 dashboard deleted" in alert, alert
    assert kept_search == "PRUNER-TEST private-1", "table state was reset by the rerun"
    assert not api.dashboard_exists(uid), "dashboard still exists in API"
    assert remaining == 0, "deleted dashboard reappeared after the check reran"
    return f"alert '{alert.strip()}'; API 404; row gone after rerun"


def flow_bulk_delete(s):
    targets = [SEEDED["private-2"], SEEDED["private-3"], SEEDED["private-4"]]
    s.goto_check(CHECK_NO_ITEMS)
    s.search("")
    total_before = s.total()
    # A selection hidden by a new search must not be deleted with it
    s.search("PRUNER-TEST shared-edit")
    s.root.locator(SEL_SELECT_ROW).first.check()
    s.search(SEARCH_PRIVATE)
    hidden_selection_cleared = s.root.locator(SEL_DELETE_SELECTED).is_disabled()
    s.root.locator(SEL_SELECT_ALL).check()
    label = s.root.locator(SEL_DELETE_SELECTED).inner_text()
    s.shot("04-bulk-selected")
    s.root.locator(SEL_DELETE_SELECTED).click()
    s.wait_alerts_gone()
    s.root.locator(SEL_CONFIRM).click()
    alert = s.alert_text()
    s.wait_for_results()
    s.search("")
    total_after = s.total()
    s.shot("05-after-bulk")
    assert hidden_selection_cleared, "selection survived a search change"
    assert "(3)" in label, f"select-all should only pick the 3 filtered rows: {label}"
    assert "3 dashboards deleted" in alert, alert
    assert not any(api.dashboard_exists(uid) for uid in targets)
    assert api.dashboard_exists(SEEDED["shared-edit"]), "unselected dashboard deleted"
    assert api.dashboard_exists(SEEDED["public-view"]), "unselected dashboard deleted"
    assert total_after == total_before - 3, f"{total_before} -> {total_after}"
    return f"'{label.strip()}' -> '{alert.strip()}'; {total_before} -> {total_after} rows"


def flow_delete_then_switch_check(s):
    # Both checks list empty never-viewed dashboards; deleting under one check
    # must not leave the row in the other check's cached result
    uid = SEEDED["public-view"]
    s.goto_check(CHECK_NOT_VIEWED)
    s.goto_check(CHECK_NO_ITEMS)
    s.search("PRUNER-TEST public-view")
    s.wait_alerts_gone()
    s.root.locator(SEL_DELETE_ROW).first.click()
    s.root.locator(SEL_CONFIRM).click()
    s.alert_text()
    s.wait_for_results()
    s.goto_check(CHECK_NOT_VIEWED)
    s.search("PRUNER-TEST public-view")
    remaining = s.total()
    s.search("")
    assert not api.dashboard_exists(uid), "dashboard still exists in API"
    assert remaining == 0, "deleted dashboard still listed by the other check"
    return "deleted under one check; not listed when switching to the other"


def flow_non_superuser(s):
    s.wait_for_results()
    notice = s.root.get_by_text("Limited to dashboards you can delete").count()
    shown = s.total()
    rows = s.root.locator(SEL_ROW).all_inner_texts()
    s.shot("06-non-superuser")
    assert notice, "non-superuser notice missing"
    assert shown == len(STATE["tester_deletable"]), f"{shown} rows: {rows}"
    assert all("shared-edit" in r for r in rows), rows
    return f"notice shown; {shown} row(s): only the dashboard shared with edit access"


def flow_no_authority(s):
    s.root.get_by_text("Missing authority").wait_for(timeout=30000)
    s.shot("07-no-authority")
    assert s.integrity_posts == 0, f"{s.integrity_posts} integrity runs started"
    return "'Missing authority' warning shown instead of running the check"


SUPERUSER_FLOWS = [
    flow_default_check,
    flow_not_viewed_check,
    flow_search_and_labels,
    flow_open_link,
    flow_single_delete,
    flow_bulk_delete,
    flow_delete_then_switch_check,
]


def run_flows(browser, user, password, flows, results):
    try:
        session = Session(browser, user, password)
    except Exception as err:
        for flow in flows:
            results.append({"flow": flow.__name__, "user": user, "status": "FAIL",
                            "detail": f"app did not open: {err}"})
            print(f"FAIL {flow.__name__}: app did not open: {err}")
        return
    try:
        for flow in flows:
            entry = {"flow": flow.__name__, "user": user}
            try:
                entry.update(status="PASS", detail=flow(session))
            except Exception as err:  # record and continue with the next flow
                entry.update(status="FAIL", detail=f"{type(err).__name__}: {err}")
                session.shot(f"fail-{flow.__name__}")
            results.append(entry)
            print(f"{entry['status']:4} {entry['flow']}: {entry['detail']}")
        unexpected = session.unexpected_errors()
        results.append({"flow": "events", "user": user, **session.events})
        results.append({
            "flow": "no_unexpected_errors", "user": user,
            "status": "FAIL" if unexpected else "PASS",
            "detail": "; ".join(e[:200] for e in unexpected) or "none",
        })
    finally:
        session.close()


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    _, info = api.get("system/info?fields=version")
    results = [{"flow": "meta", "version": info["version"], "mode": APP_MODE}]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        run_flows(browser, api.USER, api.PASSWORD, SUPERUSER_FLOWS, results)
        run_flows(browser, USERS["tester"], USERS["password"], [flow_non_superuser], results)
        run_flows(browser, USERS["viewer"], USERS["password"], [flow_no_authority], results)
        browser.close()
    with open(os.path.join(RESULTS_DIR, "results.json"), "w") as handle:
        json.dump(results, handle, indent=2)
    failed = [e for e in results if e.get("status") == "FAIL"]
    for entry in failed:
        print(f"FAIL {entry['flow']} ({entry['user']}): {entry['detail']}")
    print(f"{len(failed)} failure(s)")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
