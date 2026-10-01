"""Minimal DHIS2 Web API client for the e2e suite (stdlib only).

Configured through environment variables:
    DHIS2_URL       instance base URL, e.g. http://dhis2-agent-x:8080
    DHIS2_USER      superuser name (default: local_admin)
    DHIS2_PASSWORD  password (default: district)
"""
import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = os.environ.get("DHIS2_URL", "http://localhost:8080").rstrip("/")
USER = os.environ.get("DHIS2_USER", "local_admin")
PASSWORD = os.environ.get("DHIS2_PASSWORD", "district")
JSON_TYPE = "application/json"


def _auth_header(user, password):
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return "Basic " + token


def request(method, path, body=None, user=USER, password=PASSWORD):
    """Return (status, parsed JSON body or None). Never raises on HTTP errors."""
    data = json.dumps(body).encode() if body is not None else None
    url = f"{BASE_URL}/api/" + urllib.parse.quote(path, safe="/?&=:,[]*!-_.~")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", _auth_header(user, password))
    req.add_header("Accept", JSON_TYPE)
    if data is not None:
        req.add_header("Content-Type", JSON_TYPE)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as err:
        raw = err.read()
        try:
            return err.code, json.loads(raw) if raw else None
        except ValueError:
            return err.code, None


def get(path, **kwargs):
    return request("GET", path, **kwargs)


def post(path, body, **kwargs):
    return request("POST", path, body, **kwargs)


def delete(path, **kwargs):
    return request("DELETE", path, **kwargs)


def dashboard_exists(uid):
    status, _ = get(f"dashboards/{uid}?fields=id")
    return status == 200


def run_check(code, timeout_s=120):
    """Run an integrity check server-side and return its fresh issues list."""
    _, before = get(f"dataIntegrity/details?checks={code}")
    previous_start = (before or {}).get(code, {}).get("startTime")
    post(f"dataIntegrity/details?checks={code}", None)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        time.sleep(1)
        _, result = get(f"dataIntegrity/details?checks={code}")
        details = (result or {}).get(code)
        if details and details.get("finishedTime") and details.get("startTime") != previous_start:
            return details["issues"]
    raise TimeoutError(f"Integrity check {code} did not finish")


def session_cookie(user=USER, password=PASSWORD):
    """Authenticated session cookie via Basic-auth GET /api/me (works 2.40+)."""
    req = urllib.request.Request(f"{BASE_URL}/api/me")
    req.add_header("Authorization", _auth_header(user, password))
    with urllib.request.urlopen(req) as resp:
        for header in resp.headers.get_all("Set-Cookie") or []:
            name, _, value = header.split(";", 1)[0].partition("=")
            if "JSESSIONID" in name:
                return name.strip(), value.strip()
    raise RuntimeError("No JSESSIONID returned from /api/me")
