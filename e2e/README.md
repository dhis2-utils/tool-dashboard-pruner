# End-to-end tests

Playwright acceptance suite for the Dashboard Pruner app. It runs against a live DHIS2 instance and
**deletes dashboards and creates users and roles** — only use a disposable test instance.

Requires Python 3 with Playwright (`pip install playwright && playwright install chromium`).

## 1. Seed test data

```
DHIS2_URL=http://my-test-instance:8080 python3 e2e/seed.py
```

Creates six empty `PRUNER-TEST …` dashboards (four private ones owned by a non-superuser, one shared
with the test user with edit access, one public with view access), the users `pruner_tester` (has
`F_PERFORM_MAINTENANCE`) and `pruner_viewer` (does not), and writes the expected state to
`e2e/seed-state.json`. Rerun it before every test run.

`DHIS2_USER` / `DHIS2_PASSWORD` select the superuser (default `local_admin` / `district`).

## 2. Run the suite

Against the app installed on the instance (install `build/bundle/*.zip` first, e.g.
`curl -u admin:district -F file=@build/bundle/Dashboard-Pruner-Tool-0.2.0.zip $DHIS2_URL/api/apps`):

```
DHIS2_URL=http://my-test-instance:8080 python3 e2e/test_pruner.py
```

Against the development server (`pnpm start --proxy $DHIS2_URL`):

```
DHIS2_URL=http://my-test-instance:8080 APP_MODE=dev APP_URL=http://localhost:3000 \
    DEV_SERVER=http://localhost:8080 python3 e2e/test_pruner.py
```

Results and screenshots go to `e2e/results/` (`RESULTS_DIR` to change).
