"""Entry point of the e2e suite; run it through run.sh (see README.md).

Installs APP_ZIP, cleans up after any earlier killed run, seeds, runs the
browser flows, cleans up, uninstalls the app and writes results.json in the
shape TESTING.md (reference-tool-conventions) defines.
"""

import json
import os
import sys
import time
import zipfile
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

import dhis2api as api
import flows
from seed import StateRecord, seed_all

CONTRACT_VERSION = 1
RESULTS_DIR = os.environ.get("RESULTS_DIR", "")
APP_ZIP = os.environ.get("APP_ZIP", "")
EXIT_FAILED = 1
EXIT_ERROR = 2


class SuiteError(RuntimeError):
    """The suite could not run (exit code 2)."""


def read_manifest():
    with zipfile.ZipFile(APP_ZIP) as bundle:
        return json.loads(bundle.read("manifest.webapp"))


def install_app(manifest):
    status = api.upload_app(APP_ZIP)
    if not 200 <= status < 300:
        raise SuiteError(f"installing {APP_ZIP} failed: HTTP {status}")
    if os.environ.get("APP_KEY"):
        return os.environ["APP_KEY"]
    _, apps = api.get("apps")
    for app in apps or []:
        if app.get("name") == manifest["name"]:
            return app["key"]
    raise SuiteError(f"installed app {manifest['name']!r} not found in /api/apps")


def uninstall_app(app_key):
    status, body = api.delete(f"apps/{app_key}")
    return status in (200, 204), f"HTTP {status} {body or ''}".strip()


class Results:
    def __init__(self, label, server_version, app_key, app_version):
        self.started = time.time()
        self.data = {
            "contract_version": CONTRACT_VERSION,
            "label": label,
            "server_version": server_version,
            "app_key": app_key,
            "app_version": app_version,
        }
        self.tests = []

    def add(self, test_id, status, message):
        self.tests.append({"id": test_id, "status": status, "message": message})
        print(f"{status.upper():4} {test_id}: {message}", flush=True)

    def write(self, error=None):
        # The suite could not run: report no tests, so the counts match
        tests = [] if error else self.tests
        tally = {s: sum(1 for t in tests if t["status"] == s) for s in ("pass", "fail", "skip")}
        payload = {
            **self.data,
            "duration_s": round(time.time() - self.started),
            "total": len(tests),
            "passed": tally["pass"],
            "failed": tally["fail"],
            "skipped": tally["skip"],
            "tests": tests,
        }
        if error:
            payload["error"] = error
        with open(os.path.join(RESULTS_DIR, "results.json"), "w") as handle:
            json.dump(payload, handle, indent=2)

    @property
    def failed(self):
        return any(t["status"] == "fail" for t in self.tests)


def test_id(flow):
    return flow.__name__.replace("_", "-")


def run_session(browser, ctx, user, flow_list):
    """Open the app as `user` and run each flow; record one result per flow."""
    results, seed, label = ctx["results"], ctx["seed"], ctx["label"]
    try:
        session = flows.Session(browser, user["username"], user["password"], ctx["app_url"])
    except Exception as err:  # noqa: BLE001 - the app did not open: every flow fails
        for flow in flow_list:
            results.add(test_id(flow), "fail", f"app did not open as {user['username']}: {err}")
        return
    try:
        for flow in flow_list:
            args = (session, seed, ctx["record"]) if flow is flows.run_check_again else (session, seed)
            try:
                message = flow(*args)
                if message is None:
                    results.add(test_id(flow), "skip", "not applicable on this DHIS2 version")
                else:
                    results.add(test_id(flow), "pass", message)
            except Exception as err:  # noqa: BLE001 - record the failure and go on
                results.add(test_id(flow), "fail", f"{type(err).__name__}: {err}"[:500])
                session.shot(RESULTS_DIR, f"{label}-fail-{test_id(flow)}")
        session.shot(RESULTS_DIR, f"{label}-{user['role']}-end")
        errors = session.errors
        results.add(
            f"no-unexpected-errors-{user['role']}",
            "fail" if errors else "pass",
            "; ".join(e[:200] for e in errors[:10]) or "no console, page or HTTP errors",
        )
    finally:
        session.close()


SUPERUSER_FLOWS = [
    flows.default_check,
    flows.not_viewed_check,
    flows.search_and_labels,
    flows.xss_name_is_text,
    flows.open_link,
    flows.single_delete,
    flows.cancel_keeps_dashboard,
    flows.bulk_delete,
    flows.delete_already_deleted,
    flows.delete_then_switch_check,
    flows.run_check_again,
    flows.push_analysis_blocks_delete,
]


def run_flows(ctx):
    seed = ctx["seed"]
    users = [
        ({"role": "superuser", "username": api.USER, "password": api.PASSWORD}, SUPERUSER_FLOWS),
        ({"role": "tester", **seed.users["tester"], "password": seed.password}, [flows.non_superuser]),
        ({"role": "viewer", **seed.users["viewer"], "password": seed.password}, [flows.no_authority]),
    ]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for user, flow_list in users:
                run_session(browser, ctx, user, flow_list)
        finally:
            browser.close()


def check_superuser():
    status, me = api.get("me?fields=authorities")
    if status != 200:
        raise SuiteError(f"cannot sign in as {api.USER}: HTTP {status}")
    if "ALL" not in me.get("authorities", []):
        raise SuiteError(f"{api.USER} does not have the ALL authority")


def clean_leftovers(record):
    record.load()
    if record.objects:
        print(f"Deleting {len(record.objects)} object(s) left by an earlier run", flush=True)
    left = record.delete_all()
    if left:
        raise SuiteError("could not delete what an earlier run left: " + "; ".join(left))


def finish(results, record, app_key):
    """Clean up after the flows, and report it as two more tests."""
    try:
        left = record.delete_all()
    except Exception as err:  # noqa: BLE001 - a cleanup failure is a test failure
        left = [f"{type(err).__name__}: {err}"]
    results.add("cleanup", "fail" if left else "pass", "; ".join(left) or "everything the run created is deleted")
    try:
        uninstalled, detail = uninstall_app(app_key)
    except OSError as err:
        uninstalled, detail = False, f"{type(err).__name__}: {err}"
    results.add("uninstall", "pass" if uninstalled else "fail", f"DELETE /api/apps/{app_key}: {detail}")


def prepare():
    """Read what results.json records about this run."""
    manifest = read_manifest()
    check_superuser()
    _, info = api.get("system/info?fields=version")
    server_version = info["version"]
    label = os.environ.get("LABEL") or server_version
    return manifest, Results(label, server_version, None, manifest.get("version"))


def fail_to_run(results, err):
    """The suite could not run: report the stage error and exit with 2."""
    stage_error = f"{type(err).__name__}: {err}"
    print(f"ERROR {stage_error}", file=sys.stderr, flush=True)
    results.write(error=stage_error)
    return EXIT_ERROR


def main():
    try:
        manifest, results = prepare()
    except Exception as err:  # noqa: BLE001 - any failure here means the suite could not run
        label = os.environ.get("LABEL") or None
        return fail_to_run(Results(label, None, None, None), err)

    record = StateRecord()
    app_key = None
    try:
        clean_leftovers(record)
        app_key = install_app(manifest)
        results.data["app_key"] = app_key
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        seed = seed_all(record, run_id, app_key)
        print(f"Seeded {len(seed.dashboards)} dashboards as {seed.prefix!r}", flush=True)
        ctx = {
            "results": results,
            "seed": seed,
            "record": record,
            "label": results.data["label"],
            "app_url": f"{api.BASE_URL}/api/apps/{app_key}/index.html",
        }
        run_flows(ctx)
    except Exception as err:  # noqa: BLE001 - any failure here means the suite could not run
        try:
            record.delete_all()
            if app_key:
                uninstall_app(app_key)
        except Exception as cleanup_err:  # noqa: BLE001 - report the first error, not this one
            print(f"ERROR during cleanup: {cleanup_err}", file=sys.stderr, flush=True)
        return fail_to_run(results, err)

    finish(results, record, app_key)
    results.write()
    return EXIT_FAILED if results.failed else 0


if __name__ == "__main__":
    sys.exit(main())
