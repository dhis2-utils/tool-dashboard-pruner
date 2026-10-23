"""Browser flows for the Dashboard Pruner app (Playwright for Python).

Each flow takes a Session and the Seed, raises AssertionError on failure and
returns a short description of what it checked.
"""

import os
import re
import time

from playwright.sync_api import Error as PlaywrightError

import dhis2api as api
from seed import XSS_MARKER, XSS_NAME_SUFFIX, create_dashboard

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
SEL_ALERT_DISMISS = "[data-test='dhis2-uicore-alertbar-dismiss']"
SEL_SELECT_ALL = "[data-test='select-all'] input"
SEL_DELETE_SELECTED = "[data-test='delete-selected']"
SEL_DELETE_ROW = "[data-test='delete-row']"
SEL_CONFIRM = "[data-test='confirm-delete']"
SEL_MODAL = "[data-test='delete-modal']"
SEL_RERUN = "[data-test='rerun-check']"
SEL_HEADERS = f"{SEL_TABLE} thead th"
SEL_REFRESHING = "[data-test='refreshing']"
SEL_SELECT_ROW = "[data-test='select-row'] input"
SEL_PUSH_NOTE = "[data-test='push-analysis-note']"
APP_HEADING = "Dashboard pruner"
CHECK_TIMEOUT_MS = int(os.environ.get("CHECK_TIMEOUT_MS", "300000"))
ALERT_TIMEOUT_MS = 120000
# Platform noise that the app does not cause. HTTP errors are recorded
# separately, from the responses, so "Failed to load resource" hides nothing.
IGNORED_ERRORS = ("not a secure context", "logo_banner", "Failed to load resource")
# Up to 2.41 the app looks up dashboards by id; 404 means "deleted since the
# check ran" and is handled. The header bar asks for a custom logo, which an
# instance may not have.
EXPECTED_HTTP = [
    re.compile(r"^404 GET .*/api/\d+/dashboards/[A-Za-z0-9]{11}\?fields="),
    re.compile(r"^404 GET .*/api/(\d+/)?staticContent/logo_banner"),
]


class Session:
    """One logged-in browser context, with its errors captured."""

    def __init__(self, browser, user, password, app_url):
        self.context = browser.new_context(viewport={"width": 1400, "height": 1000})
        self.errors = []
        self.integrity_posts = 0
        self.page = self.context.new_page()
        self.page.on("console", self._on_console)
        self.page.on("pageerror", lambda e: self.errors.append(f"pageerror: {e}"))
        self.page.on("response", self._on_response)
        self.page.on("request", self._on_request)
        self.expected_http = list(EXPECTED_HTTP)
        name, value = api.session_cookie(user, password)
        host = re.sub(r"^https?://", "", api.BASE_URL).split("/")[0].split(":")[0]
        self.context.add_cookies([{"name": name, "value": value, "domain": host, "path": "/"}])
        self.page.goto(app_url)
        self.root = self._find_app_frame()

    def _on_console(self, msg):
        if msg.type == "error" and not any(n in msg.text for n in IGNORED_ERRORS):
            self.errors.append(f"console: {msg.text}")

    def _on_request(self, req):
        if req.method == "POST" and "/dataIntegrity" in req.url:
            self.integrity_posts += 1

    def _on_response(self, resp):
        if resp.status >= 400:
            line = f"{resp.status} {resp.request.method} {resp.url}"
            if not any(p.match(line) for p in self.expected_http):
                self.errors.append(line)

    def _find_app_frame(self, timeout_s=120):
        # 2.42+ serves installed apps inside the global-shell iframe; 2.41
        # and earlier at the top level
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            for frame in self.page.frames:
                try:
                    if frame.locator("h1", has_text=APP_HEADING).count():
                        return frame
                except PlaywrightError:
                    # The frame detached while navigating
                    continue
            time.sleep(0.5)
        raise TimeoutError("The app did not render")

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
        """Row count from the pagination footer (the table pages client-side)."""
        if self.root.locator(SEL_EMPTY).count():
            return 0
        text = self.root.locator(SEL_PAGINATION).inner_text()
        return int(re.search(r"of (\d+)\s*$", text.strip()).group(1))

    def search(self, term):
        # Filtering is synchronous client-side; wait until the input holds it
        self.root.locator(SEL_SEARCH).fill(term)
        self.root.wait_for_function(
            "([sel, v]) => document.querySelector(sel)?.value === v",
            arg=[SEL_SEARCH, term],
        )

    def headers(self):
        return [h.strip() for h in self.root.locator(SEL_HEADERS).all_inner_texts()]

    def wait_alerts_gone(self):
        # Success alerts hide by themselves, critical ones stay until closed.
        # A lingering one would be mistaken for the next result.
        self.dismiss_alerts()
        self.root.locator(SEL_ALERT).first.wait_for(state="detached", timeout=ALERT_TIMEOUT_MS)

    def dismiss_alerts(self):
        dismiss = self.root.locator(SEL_ALERT_DISMISS)
        while (count := dismiss.count()) > 0:
            dismiss.first.click()
            self.root.wait_for_function(
                "([sel, n]) => document.querySelectorAll(sel).length < n",
                arg=[SEL_ALERT_DISMISS, count],
                timeout=ALERT_TIMEOUT_MS,
            )

    def alert_text(self):
        alert = self.root.locator(SEL_ALERT).last
        alert.wait_for(timeout=ALERT_TIMEOUT_MS)
        return alert.inner_text()

    def confirm_delete(self):
        self.wait_alerts_gone()
        self.root.locator(SEL_CONFIRM).click()
        alert = self.alert_text()
        self.wait_for_results()
        return alert

    def shot(self, results_dir, name):
        self.page.screenshot(path=os.path.join(results_dir, f"{name}.png"), full_page=True)

    def close(self):
        self.context.close()


def default_check(s, seed):
    s.wait_for_results()
    expected = len(api.run_check(CHECK_NO_ITEMS))
    s.search("")
    shown = s.total()
    assert shown == expected, f"table shows {shown}, API reports {expected}"
    assert not any("Last viewed" in h for h in s.headers()), s.headers()
    s.search(seed.prefix)
    seeded = s.total()
    assert seeded == len(seed.dashboards), f"{seeded} of {len(seed.dashboards)} seeded dashboards listed"
    return f"{shown} empty dashboards listed (API: {expected}), all {seeded} seeded ones among them"


def not_viewed_check(s, seed):
    s.search("")
    s.root.locator(SEL_CHECK_SELECT).locator(SEL_SELECT_INPUT).click()
    s.root.get_by_text("Dashboards not viewed in one year").last.click()
    s.wait_for_check(CHECK_NOT_VIEWED)
    expected = len(api.run_check(CHECK_NOT_VIEWED))
    shown = s.total()
    assert shown == expected, f"table shows {shown}, API reports {expected}"
    assert any("Last viewed" in h for h in s.headers()), s.headers()
    s.search(seed.name("shared-edit"))
    row = s.root.locator(SEL_ROW).first.inner_text()
    s.search("")
    assert "Never" in row, f"a dashboard nobody opened should show 'Never': {row}"
    return f"{shown} stale dashboards listed (API: {expected}); never-viewed shown as 'Never'"


def search_and_labels(s, seed):
    s.goto_check(CHECK_NO_ITEMS)
    s.search(seed.name("private"))
    private = s.total()
    s.search(seed.name("public-view"))
    label = s.root.locator(SEL_ROW).first.inner_text()
    s.search("no dashboard is called this " + seed.prefix)
    no_match = s.root.locator(SEL_EMPTY).inner_text()
    s.search("")
    assert private == 4, f"expected 4 private test dashboards, got {private}"
    assert "Public (can view)" in label, label
    assert "No dashboards match the search" in no_match, no_match
    return "search narrows to 4 rows; public read-only shown as 'Public (can view)'"


def xss_name_is_text(s, seed):
    s.goto_check(CHECK_NO_ITEMS)
    s.search(seed.name("xss"))
    row = s.root.locator(SEL_ROW).first.inner_text()
    images = s.root.locator(f"{SEL_ROW} img").count()
    executed = s.root.evaluate(f"() => window.{XSS_MARKER} === 1")
    s.search("")
    assert not executed, "script in a dashboard name ran"
    assert images == 0, "markup in a dashboard name was rendered as HTML"
    assert XSS_NAME_SUFFIX in row, f"name not shown as text: {row}"
    return "markup in a dashboard name is shown as text and does not run"


def open_link(s, seed):
    s.search(seed.name("shared-edit"))
    href = s.root.locator(f"{SEL_ROW} a").first.get_attribute("href")
    resp = s.context.request.get(href)
    s.search("")
    assert href.endswith(f"/dhis-web-dashboard/#/{seed.dashboards['shared-edit']}"), href
    assert resp.ok, f"{resp.status} for {href}"
    return f"link {href} -> HTTP {resp.status}"


def single_delete(s, seed):
    uid = seed.dashboards["private-1"]
    s.goto_check(CHECK_NO_ITEMS)
    s.search(seed.name("private-1"))
    s.root.locator(SEL_DELETE_ROW).first.click()
    s.root.locator(SEL_MODAL).wait_for()
    modal = s.root.locator(SEL_MODAL).inner_text()
    alert = s.confirm_delete()
    kept_search = s.root.locator(SEL_SEARCH).input_value()
    remaining = s.total()
    s.search("")
    assert seed.name("private-1") in modal, f"dialog does not name the dashboard: {modal}"
    assert "1 dashboard deleted" in alert, alert
    assert kept_search == seed.name("private-1"), "table state was reset by the rerun"
    assert not api.dashboard_exists(uid), "dashboard still exists in API"
    assert remaining == 0, "deleted dashboard reappeared after the check reran"
    return f"alert '{alert.strip()}'; API 404; row gone after rerun"


def cancel_keeps_dashboard(s, seed):
    s.goto_check(CHECK_NO_ITEMS)
    s.search(seed.name("private-2"))
    s.root.locator(SEL_DELETE_ROW).first.click()
    s.root.locator(SEL_MODAL).wait_for()
    s.root.get_by_role("button", name="Cancel").click()
    s.root.locator(SEL_MODAL).wait_for(state="detached")
    remaining = s.total()
    s.search("")
    assert api.dashboard_exists(seed.dashboards["private-2"]), "cancel deleted the dashboard"
    assert remaining == 1, "row disappeared after cancel"
    return "cancel closes the dialog and deletes nothing"


def bulk_delete(s, seed):
    targets = [seed.dashboards[k] for k in ("private-2", "private-3", "private-4")]
    s.goto_check(CHECK_NO_ITEMS)
    s.search("")
    total_before = s.total()
    # A selection hidden by a new search must not be deleted with it
    s.search(seed.name("shared-edit"))
    s.root.locator(SEL_SELECT_ROW).first.check()
    s.search(seed.name("private"))
    hidden_selection_cleared = s.root.locator(SEL_DELETE_SELECTED).is_disabled()
    s.root.locator(SEL_SELECT_ALL).check()
    label = s.root.locator(SEL_DELETE_SELECTED).inner_text()
    s.root.locator(SEL_DELETE_SELECTED).click()
    alert = s.confirm_delete()
    s.search("")
    total_after = s.total()
    assert hidden_selection_cleared, "selection survived a search change"
    assert "(3)" in label, f"select-all should only pick the 3 filtered rows: {label}"
    assert "3 dashboards deleted" in alert, alert
    assert not any(api.dashboard_exists(uid) for uid in targets), "a selected dashboard still exists"
    for kept in ("shared-edit", "public-view"):
        assert api.dashboard_exists(seed.dashboards[kept]), f"unselected dashboard {kept} deleted"
    assert total_after == total_before - 3, f"{total_before} -> {total_after}"
    return f"'{label.strip()}' -> '{alert.strip()}'; {total_before} -> {total_after} rows"


def delete_already_deleted(s, seed):
    # Someone else deletes the dashboard after the check ran: the app must
    # report it and recover, not crash or keep listing it
    uid = seed.dashboards["gone"]
    s.goto_check(CHECK_NO_ITEMS)
    s.search(seed.name("gone"))
    s.root.locator(SEL_DELETE_ROW).first.click()
    s.root.locator(SEL_MODAL).wait_for()
    status, _ = api.delete(f"dashboards/{uid}")
    assert status in (200, 204), f"could not delete behind the app's back: HTTP {status}"
    s.expected_http.append(re.compile(rf"^404 DELETE .*/dashboards/{uid}$"))
    alert = s.confirm_delete()
    remaining = s.total()
    s.search("")
    assert "1 dashboard deleted" in alert, f"a dashboard that is already gone counts as deleted: {alert}"
    assert remaining == 0, "dashboard deleted elsewhere is still listed after the rerun"
    return f"alert '{alert.strip()}'; row gone after rerun"


def delete_then_switch_check(s, seed):
    # Both checks list empty never-viewed dashboards; deleting under one check
    # must not leave the row in the other check's cached result
    uid = seed.dashboards["public-view"]
    s.goto_check(CHECK_NOT_VIEWED)
    s.goto_check(CHECK_NO_ITEMS)
    s.search(seed.name("public-view"))
    s.root.locator(SEL_DELETE_ROW).first.click()
    s.confirm_delete()
    s.goto_check(CHECK_NOT_VIEWED)
    s.search(seed.name("public-view"))
    remaining = s.total()
    s.search("")
    assert not api.dashboard_exists(uid), "dashboard still exists in API"
    assert remaining == 0, "deleted dashboard still listed by the other check"
    return "deleted under one check; not listed when switching to the other"


def run_check_again(s, seed, record):
    s.goto_check(CHECK_NO_ITEMS)
    create_dashboard(record, seed, "created-later")
    s.search(seed.name("created-later"))
    before = s.total()
    s.root.locator(SEL_RERUN).click()
    s.wait_for_results()
    after = s.total()
    s.search("")
    assert before == 0, "a dashboard created after the check was listed before rerunning"
    assert after == 1, "'Run check again' did not pick up a new empty dashboard"
    return "a dashboard created after the check appears after 'Run check again'"


def push_analysis_blocks_delete(s, seed):
    if not seed.push_analysis:
        return None
    s.goto_check(CHECK_NO_ITEMS)
    s.search(seed.name("push"))
    row = s.root.locator(SEL_ROW).first
    text = row.locator(SEL_PUSH_NOTE).inner_text()
    checkbox_disabled = row.locator(SEL_SELECT_ROW).is_disabled()
    delete_disabled = row.locator(SEL_DELETE_ROW).is_disabled()
    select_all_disabled = s.root.locator(SEL_SELECT_ALL).is_disabled()
    s.search("")
    assert seed.name("push analysis") in text, text
    assert checkbox_disabled and delete_disabled, "blocked row can still be deleted"
    assert select_all_disabled, "select-all is enabled with only a blocked row"
    assert api.dashboard_exists(seed.dashboards["push"])
    return f"note '{text.strip()}'; checkbox, delete and select-all disabled"


def non_superuser(s, seed):
    s.wait_for_results()
    notice = s.root.get_by_text("Limited to dashboards you can delete").count()
    shown = s.total()
    tester = {"user": seed.users["tester"]["username"], "password": seed.password}
    _, visible = api.get("dashboards?fields=id,access[delete]&paging=false", **tester)
    deletable = {d["id"] for d in visible["dashboards"] if d["access"]["delete"]}
    expected = len([i for i in api.run_check(CHECK_NO_ITEMS) if i["id"] in deletable])
    s.search(seed.prefix)
    rows = s.root.locator(SEL_ROW).all_inner_texts()
    s.search("")
    assert notice, "non-superuser notice missing"
    assert shown == expected, f"{shown} rows, but the user can delete {expected} flagged dashboards"
    assert len(rows) == 1 and seed.name("shared-edit") in rows[0], f"seeded rows shown: {rows}"
    return f"notice shown; {shown} row(s), of the seeded ones only the one shared with edit access"


def no_authority(s, seed):
    s.root.get_by_text("Missing authority").wait_for(timeout=60000)
    assert s.integrity_posts == 0, f"{s.integrity_posts} integrity runs started"
    return "'Missing authority' warning shown instead of running the check"
