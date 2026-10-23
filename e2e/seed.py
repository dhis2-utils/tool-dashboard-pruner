"""Seeding and cleanup for the e2e suite.

Every object gets a run-unique name and a client-side UID, and is recorded
in the dataStore (e2e-state/tool-dashboard-pruner) before it is created. A
run starts by deleting whatever an earlier, killed run left in the record.
"""

import secrets
from dataclasses import dataclass, field

import dhis2api as api

STATE_NAMESPACE = "e2e-state"
STATE_KEY = "tool-dashboard-pruner"
STATE_PATH = f"dataStore/{STATE_NAMESPACE}/{STATE_KEY}"
FIXED_PREFIX = "E2E tool-dashboard-pruner"
# Delete in this order: a push analysis blocks deleting its dashboard, and a
# user can't be deleted while a dashboard is owned by them
DELETE_ORDER = ["pushAnalysis", "dashboards", "users", "userRoles"]
# Push analysis was removed in 2.43
PUSH_ANALYSIS_REMOVED_IN = 43
XSS_MARKER = "__e2eXss"
XSS_NAME_SUFFIX = f'xss <img src=x onerror="window.{XSS_MARKER}=1">'

# name suffix -> (owner, public sharing, access granted to the tester)
# The private dashboards belong to the viewer and are shared with nobody, so
# the superuser running the app has no sharing-based access to them.
VIEWER = "viewer"
DASHBOARDS = {
    "private-1": (VIEWER, "--------", None),
    "private-2": (VIEWER, "--------", None),
    "private-3": (VIEWER, "--------", None),
    "private-4": (VIEWER, "--------", None),
    "shared-edit": (None, "--------", "rw------"),
    "public-view": (None, "r-------", None),
    "gone": (None, "--------", None),
    # Up to 2.42 this one also gets a push analysis, which blocks deleting it
    "push": (None, "--------", None),
    XSS_NAME_SUFFIX: (None, "--------", None),
}


class SeedError(RuntimeError):
    """Seeding or cleanup could not be done: the suite can't run."""


def _expect(status, body, ok=(200, 201)):
    if status not in ok:
        raise SeedError(f"HTTP {status}: {body}")


class StateRecord:
    """The record of what this suite created, kept on the instance."""

    def __init__(self):
        self.objects = []

    def _save(self):
        payload = {"objects": self.objects}
        status, body = api.put(STATE_PATH, payload)
        if status == 404:
            status, body = api.post(STATE_PATH, payload)
        _expect(status, body)

    def add(self, kind, uid):
        self.objects.append({"type": kind, "id": uid})
        self._save()

    def load(self):
        status, body = api.get(STATE_PATH)
        self.objects = (body or {}).get("objects", []) if status == 200 else []

    def delete_all(self):
        """Delete every recorded object, then the record. Returns what is left."""
        left = []
        for obj in [o for o in self.objects if o["type"] == "users"]:
            left += _delete_jobs_of(obj["id"])
        for kind in DELETE_ORDER:
            for obj in [o for o in self.objects if o["type"] == kind]:
                status, body = api.delete(f"{kind}/{obj['id']}")
                if status not in (200, 204, 404):
                    left.append(f"{kind}/{obj['id']}: HTTP {status} {body}")
        if left:
            # Keep the record so the next run tries again
            self.objects = [o for o in self.objects if any(o["id"] in m for m in left)]
            self._save()
        else:
            api.delete(STATE_PATH)
            self.objects = []
        return left


def _delete_jobs_of(user_id):
    """Delete the one-off jobs a user's integrity runs left behind.

    Running a check creates a job configuration that references the user,
    and DHIS2 refuses to delete a user that one references.
    """
    left = []
    for prop in ("lastUpdatedBy", "createdBy"):
        status, body = api.get(
            f"jobConfigurations?fields=id,schedulingType&paging=false&filter={prop}.id:eq:{user_id}"
        )
        for job in (body or {}).get("jobConfigurations", []) if status == 200 else []:
            if job.get("schedulingType") != "ONCE_ASAP":
                left.append(f"jobConfigurations/{job['id']}: a scheduled job references user {user_id}")
                continue
            status, body = api.delete(f"jobConfigurations/{job['id']}")
            if status not in (200, 204, 404):
                left.append(f"jobConfigurations/{job['id']}: HTTP {status} {body}")
    return left


@dataclass
class Seed:
    prefix: str
    password: str
    users: dict = field(default_factory=dict)
    dashboards: dict = field(default_factory=dict)
    push_analysis: str | None = None
    app_authority: str = ""

    def name(self, suffix):
        return f"{self.prefix} {suffix}"


def _create(record, kind, payload, **auth):
    payload = {"id": api.new_uid(), **payload}
    record.add(kind, payload["id"])
    status, body = api.post(kind, payload, **auth)
    _expect(status, body)
    return payload["id"]


def _set_sharing(uid, public, user_accesses, **auth):
    _, sharing = api.get(f"sharing?type=dashboard&id={uid}", **auth)
    obj = sharing["object"]
    obj["publicAccess"] = public
    obj["userAccesses"] = user_accesses
    obj["userGroupAccesses"] = []
    status, body = api.post(f"sharing?type=dashboard&id={uid}", {"object": obj}, **auth)
    _expect(status, body, ok=(200,))


def app_authority(app_key):
    """The authority that opens the app, as the server names it.

    DHIS2 names it M_ plus the key without its non-alphanumeric characters.
    Read it from the server where possible: 2.41 answers /api/authorities
    with a 500 until a Struts page has been loaded. A wrong name fails the
    non-superuser flows, which open the app with it.
    """
    wanted = "M_" + "".join(c for c in app_key if c.isalnum())
    status, body = api.get("authorities")
    if status != 200:
        return wanted
    for authority in body["systemAuthorities"]:
        if authority["id"].lower() == wanted.lower():
            return authority["id"]
    raise SeedError(f"No app authority {wanted} after installing {app_key}")


def _create_users(record, seed, run_id):
    # Users don't need an organisation unit for this app; give them the
    # root when there is one, as a real user would have
    _, roots = api.get("organisationUnits?fields=id&filter=level:eq:1&paging=false")
    org_units = [{"id": ou["id"]} for ou in roots["organisationUnits"][:1]]
    roles = {
        "tester": ["F_PERFORM_MAINTENANCE", "F_DASHBOARD_PUBLIC_ADD", seed.app_authority],
        "viewer": ["F_DASHBOARD_PUBLIC_ADD", seed.app_authority],
    }
    for kind, authorities in roles.items():
        role = _create(record, "userRoles", {"name": seed.name(f"{kind} role"), "authorities": authorities})
        username = f"e2e_pruner_{kind}_{run_id.lower()}"
        uid = _create(record, "users", {
            "firstName": seed.prefix,
            "surname": kind,
            "username": username,
            "password": seed.password,
            "userRoles": [{"id": role}],
            "organisationUnits": org_units,
        })
        seed.users[kind] = {"id": uid, "username": username}


def _create_dashboards(record, seed):
    tester_id = seed.users["tester"]["id"]
    for suffix, (owner, public, tester_access) in DASHBOARDS.items():
        auth = {}
        if owner:
            auth = {"user": seed.users[owner]["username"], "password": seed.password}
        uid = _create(record, "dashboards", {"name": seed.name(suffix)}, **auth)
        accesses = [{"id": tester_id, "access": tester_access}] if tester_access else []
        _set_sharing(uid, public, accesses, **auth)
        seed.dashboards[suffix] = uid


def create_dashboard(record, seed, suffix):
    """One more private, empty dashboard, owned by the superuser."""
    uid = _create(record, "dashboards", {"name": seed.name(suffix)})
    _set_sharing(uid, "--------", [])
    seed.dashboards[suffix] = uid
    return uid


def seed_all(record, run_id, app_key):
    seed = Seed(
        prefix=f"{FIXED_PREFIX} {run_id}",
        # Meets the password policy: upper, lower, digit, special, 8+ chars
        password="E2e-" + secrets.token_hex(8) + "!Aa1",
        app_authority=app_authority(app_key),
    )
    _create_users(record, seed, run_id)
    _create_dashboards(record, seed)
    if api.server_minor_version() < PUSH_ANALYSIS_REMOVED_IN:
        seed.push_analysis = _create(record, "pushAnalysis", {
            "name": seed.name("push analysis"),
            "title": seed.name("push analysis"),
            "dashboard": {"id": seed.dashboards["push"]},
            "recipientUserGroups": [],
        })
    _verify(seed)
    return seed


def _verify(seed):
    """Read back what was seeded: a 2xx alone doesn't prove the write."""
    for suffix, uid in seed.dashboards.items():
        status, body = api.get(f"dashboards/{uid}?fields=name,sharing[public]")
        if status != 200 or body["name"] != seed.name(suffix):
            raise SeedError(f"Seeded dashboard {suffix} reads back as {status} {body}")
    if seed.push_analysis:
        status, body = api.get(f"pushAnalysis/{seed.push_analysis}?fields=dashboard[id]")
        if status != 200 or body.get("dashboard", {}).get("id") != seed.dashboards["push"]:
            raise SeedError(f"Seeded push analysis reads back as {status} {body}")
