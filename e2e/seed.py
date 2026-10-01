"""Seed test dashboards and users for the e2e suite; writes seed-state.json.

Idempotent: removes earlier PRUNER-TEST dashboards first. Run against a
disposable instance only — it creates users and dashboards.
"""
import json
import os

import dhis2api as api

PREFIX = "PRUNER-TEST"
TESTER = "pruner_tester"
VIEWER = "pruner_viewer"
TEST_PASSWORD = "Pruner-Test-1234"
# Authority to open the installed app (M_<app key>)
APP_AUTHORITY = "M_DashboardPrunerTool"
STATE_FILE = os.path.join(os.path.dirname(__file__), "seed-state.json")

# name suffix -> (owner, public sharing, access granted to the tester)
# The private dashboards belong to the viewer and are shared with nobody, so
# the superuser running the app has no sharing-based access to them.
DASHBOARDS = {
    "private-1": (VIEWER, "--------", None),
    "private-2": (VIEWER, "--------", None),
    "private-3": (VIEWER, "--------", None),
    "private-4": (VIEWER, "--------", None),
    "shared-edit": (None, "--------", "rw------"),
    "public-view": (None, "r-------", None),
}


def remove_old_dashboards():
    # Up to 2.41 list queries only return dashboards shared with the caller,
    # even for superusers, so also list as the owner of the private ones
    for auth in ({}, {"user": VIEWER, "password": TEST_PASSWORD}):
        status, body = api.get(
            f"dashboards?fields=id&paging=false&filter=name:like:{PREFIX}", **auth
        )
        for dashboard in (body or {}).get("dashboards", []) if status == 200 else []:
            api.delete(f"dashboards/{dashboard['id']}")


def ensure_role(name, authorities):
    _, body = api.get(f"userRoles?fields=id,name&filter=name:eq:{name}")
    payload = {"name": name, "authorities": authorities}
    if body["userRoles"]:
        uid = body["userRoles"][0]["id"]
        status, body = api.request("PUT", f"userRoles/{uid}", payload)
        assert status == 200, body
        return uid
    status, body = api.post("userRoles", payload)
    assert status in (200, 201), body
    return body["response"]["uid"]


def ensure_user(username, role_id, root_ou):
    _, body = api.get(f"users?fields=id&filter=username:eq:{username}")
    if body["users"]:
        return body["users"][0]["id"]
    payload = {
        "firstName": "Pruner",
        "surname": username,
        "username": username,
        "password": TEST_PASSWORD,
        "userRoles": [{"id": role_id}],
        "organisationUnits": [{"id": root_ou}],
    }
    status, body = api.post("users", payload)
    assert status in (200, 201), body
    return body["response"]["uid"]


def create_dashboard(suffix, owner, public, tester_access, tester_id):
    auth = {"user": owner, "password": TEST_PASSWORD} if owner else {}
    status, body = api.post("dashboards", {"name": f"{PREFIX} {suffix}"}, **auth)
    assert status in (200, 201), body
    uid = body["response"]["uid"]
    _, sharing = api.get(f"sharing?type=dashboard&id={uid}", **auth)
    obj = sharing["object"]
    obj["publicAccess"] = public
    obj["userAccesses"] = (
        [{"id": tester_id, "access": tester_access}] if tester_access else []
    )
    obj["userGroupAccesses"] = []
    status, body = api.post(f"sharing?type=dashboard&id={uid}", {"object": obj}, **auth)
    assert status == 200, body
    return uid


def superuser_access(uid):
    """What the superuser may do with a dashboard nobody shared with them."""
    status, body = api.get(f"dashboards/{uid}?fields=sharing[owner,public,users],access")
    return {"status": status, **(body or {})}


def main():
    remove_old_dashboards()
    _, roots = api.get("organisationUnits?fields=id&filter=level:eq:1")
    root_ou = roots["organisationUnits"][0]["id"]
    tester_role = ensure_role(
        "Pruner tester", ["F_PERFORM_MAINTENANCE", "F_DASHBOARD_PUBLIC_ADD", APP_AUTHORITY]
    )
    viewer_role = ensure_role("Pruner viewer", ["F_DASHBOARD_PUBLIC_ADD", APP_AUTHORITY])
    tester_id = ensure_user(TESTER, tester_role, root_ou)
    ensure_user(VIEWER, viewer_role, root_ou)

    dashboards = {
        suffix: create_dashboard(suffix, owner, public, access, tester_id)
        for suffix, (owner, public, access) in DASHBOARDS.items()
    }

    # Expectations come from what the server actually reports after seeding
    _, read_back = api.get(
        f"dashboards?fields=id,name,sharing[public]&paging=false&filter=name:like:{PREFIX}"
    )
    _, tester_view = api.get(
        "dashboards?fields=id,access[delete]&paging=false"
        f"&filter=name:like:{PREFIX}",
        user=TESTER,
        password=TEST_PASSWORD,
    )
    empty_ids = {issue["id"] for issue in api.run_check("dashboards_no_items")}
    state = {
        "dashboards": dashboards,
        "read_back": read_back["dashboards"],
        "tester_deletable": sorted(
            d["id"] for d in tester_view["dashboards"] if d["access"]["delete"]
        ),
        "all_seeded_flagged_empty": all(uid in empty_ids for uid in dashboards.values()),
        "empty_check_total": len(empty_ids),
        "superuser_on_foreign_private": superuser_access(dashboards["private-1"]),
        "users": {"tester": TESTER, "viewer": VIEWER, "password": TEST_PASSWORD},
    }
    with open(STATE_FILE, "w") as handle:
        json.dump(state, handle, indent=2)
    keys = ("tester_deletable", "all_seeded_flagged_empty", "empty_check_total",
            "superuser_on_foreign_private")
    print(json.dumps({k: state[k] for k in keys}, indent=1))


if __name__ == "__main__":
    main()
