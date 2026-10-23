"""Minimal DHIS2 Web API client for the e2e suite (standard library only).

Reads DHIS2_URL, DHIS2_USER and DHIS2_PASS from the environment. None of
them has a default: run.sh checks that they are set.
"""

import base64
import json
import os
import secrets
import string
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = os.environ.get("DHIS2_URL", "").rstrip("/")
USER = os.environ.get("DHIS2_USER", "")
PASSWORD = os.environ.get("DHIS2_PASS", "")
JSON_TYPE = "application/json"
TIMEOUT_S = 300
UID_FIRST = string.ascii_letters
UID_REST = string.ascii_letters + string.digits


def new_uid():
    """A DHIS2 UID, assigned client-side so it can be recorded before use."""
    return secrets.choice(UID_FIRST) + "".join(secrets.choice(UID_REST) for _ in range(10))


def _auth_header(user, password):
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return "Basic " + token


def _open(req):
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()


def _parse(raw):
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return None


def request(method, path, body=None, user=None, password=None):
    """Return (status, parsed JSON body or None). Never raises on HTTP errors."""
    data = json.dumps(body).encode() if body is not None else None
    url = f"{BASE_URL}/api/" + urllib.parse.quote(path, safe="/?&=:,[]*!-_.~")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", _auth_header(user or USER, password or PASSWORD))
    req.add_header("Accept", JSON_TYPE)
    if data is not None:
        req.add_header("Content-Type", JSON_TYPE)
    status, raw = _open(req)
    return status, _parse(raw)


def get(path, **kwargs):
    return request("GET", path, **kwargs)


def post(path, body, **kwargs):
    return request("POST", path, body, **kwargs)


def put(path, body, **kwargs):
    return request("PUT", path, body, **kwargs)


def delete(path, **kwargs):
    return request("DELETE", path, **kwargs)


def upload_app(zip_path):
    """POST /api/apps as multipart/form-data. Returns the HTTP status."""
    boundary = "----e2e" + secrets.token_hex(8)
    with open(zip_path, "rb") as handle:
        content = handle.read()
    name = os.path.basename(zip_path)
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'
        "Content-Type: application/zip\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"{BASE_URL}/api/apps", data=body, method="POST")
    req.add_header("Authorization", _auth_header(USER, PASSWORD))
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    status, _ = _open(req)
    return status


def server_minor_version():
    _, info = get("system/info?fields=version")
    return int(info["version"].split(".")[1].split("-")[0])


def dashboard_exists(uid):
    status, _ = get(f"dashboards/{uid}?fields=id")
    return status == 200


def run_check(code, timeout_s=300):
    """Run an integrity check server-side and return the issues of that run.

    GET only reads the server's cached result, which is not cleared when a
    rerun starts, so wait for a result with a new startTime.
    """
    _, before = get(f"dataIntegrity/details?checks={code}")
    previous_start = ((before or {}).get(code) or {}).get("startTime")
    post(f"dataIntegrity/details?checks={code}", None)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        time.sleep(1)
        _, result = get(f"dataIntegrity/details?checks={code}")
        details = (result or {}).get(code)
        if details and details.get("finishedTime") and details.get("startTime") != previous_start:
            return details["issues"]
    raise TimeoutError(f"Integrity check {code} did not finish in {timeout_s} s")


def session_cookie(user, password):
    """An authenticated session cookie, from a Basic-auth GET /api/me."""
    req = urllib.request.Request(f"{BASE_URL}/api/me?fields=id")
    req.add_header("Authorization", _auth_header(user, password))
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        for header in resp.headers.get_all("Set-Cookie") or []:
            name, _, value = header.split(";", 1)[0].partition("=")
            if "SESSION" in name.upper():
                return name.strip(), value.strip()
    raise RuntimeError("No session cookie returned from /api/me")
