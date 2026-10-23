#!/usr/bin/env bash
# e2e entry point (contract version 1, see e2e/README.md).
# Changes and deletes data: run it against a throwaway DHIS2 instance only.
set -u

missing=()
for var in DHIS2_URL DHIS2_USER DHIS2_PASS APP_ZIP RESULTS_DIR; do
    [ -n "${!var:-}" ] || missing+=("$var")
done
if [ ${#missing[@]} -gt 0 ]; then
    echo "Missing environment variables: ${missing[*]} (see e2e/README.md)" >&2
    exit 2
fi
case "$APP_ZIP" in
    /*) ;;
    *) echo "APP_ZIP must be an absolute path: $APP_ZIP" >&2; exit 2 ;;
esac
if [ ! -f "$APP_ZIP" ]; then
    echo "APP_ZIP not found: $APP_ZIP" >&2
    exit 2
fi
if [ ! -d "$RESULTS_DIR" ]; then
    echo "RESULTS_DIR is not an existing directory: $RESULTS_DIR" >&2
    exit 2
fi
if ! python3 -c 'import playwright' 2>/dev/null; then
    echo "Playwright for Python is missing: pip install -r e2e/requirements.txt && python3 -m playwright install chromium" >&2
    exit 2
fi

export DHIS2_URL="${DHIS2_URL%/}"
exec python3 "$(dirname "$0")/run.py"
