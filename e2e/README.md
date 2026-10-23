> [!WARNING]
> This suite creates and deletes dashboards, users, user roles and push analyses, and installs and uninstalls the app. Only run it against a throwaway DHIS2 instance that you can reset or recreate. Never run it against a production, shared or play server.

# End-to-end tests

The suite installs the built app on a DHIS2 instance and drives it in Chromium through Playwright for Python. It checks every result against the server through the API. `run.sh` follows the e2e contract (version 1) of [TESTING.md](https://github.com/dhis2-utils/reference-tool-conventions/blob/main/TESTING.md) in reference-tool-conventions.

## Get a throwaway instance

Start a local DHIS2 instance, for example on port 8080, as described in [DHIS2 in Docker](https://developers.dhis2.org/docs/tutorials/dhis2-docker/). An empty database works; so does a demo database.

## Install the dependencies

The suite needs Python 3.10 or later.

```
pip install -r e2e/requirements.txt
python3 -m playwright install chromium
```

## Run it

Build the app first (`pnpm run build`), then:

```
DHIS2_URL=http://localhost:8080 DHIS2_USER=admin DHIS2_PASS=district \
LABEL=2.42 RESULTS_DIR=/tmp/out APP_ZIP=$PWD/build/bundle/tool-dashboard-pruner-1.0.0.zip \
  e2e/run.sh
```

| Variable                   | Required | Meaning                                                            |
| -------------------------- | -------- | ------------------------------------------------------------------ |
| `DHIS2_URL`                | yes      | Instance base URL                                                  |
| `DHIS2_USER`, `DHIS2_PASS` | yes      | A user with the `ALL` authority                                    |
| `APP_ZIP`                  | yes      | Absolute path of the built bundle                                  |
| `RESULTS_DIR`              | yes      | Existing directory for `results.json` and screenshots              |
| `LABEL`                    | no       | Label for output and screenshot names; default: the server version |
| `APP_KEY`                  | no       | Default: the key the server reports for the installed app          |
| `CHECK_TIMEOUT_MS`         | no       | How long to wait for an integrity check; default 300000            |

Exit code 0 means every test passed, 1 that at least one failed, and 2 that the suite could not run (`results.json` then has an `error` field).

## What it does

1. Deletes whatever an earlier, killed run left behind, using the record in the dataStore at `e2e-state/tool-dashboard-pruner`.
2. Installs `APP_ZIP` and reads the app key from `/api/apps`.
3. Seeds two user roles, two users, nine empty dashboards and, on 2.42 and earlier, a push analysis. Every name starts with `E2E tool-dashboard-pruner <run id>`, and each object is recorded before it is created.
4. Runs the flows in `flows.py`: as a superuser, as a user with the maintenance authority, and as a user without it.
5. Deletes everything it created, and the one-off integrity jobs its users started, then uninstalls the app.

The flows cover both checks, search, public access labels, a dashboard name with HTML in it, the **Open** link, single and bulk deletes, cancel, a dashboard deleted by someone else while the dialog is open, switching checks after a delete, **Run check again**, dashboards blocked by a push analysis, the non-superuser and missing-authority views, and the absence of console and HTTP errors.
