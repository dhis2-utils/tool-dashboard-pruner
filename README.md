# DHIS2 Dashboard Pruner App

> ![Maturity: Experimental](https://img.shields.io/badge/maturity-Experimental-orange)  
> Intended use: tool to prune dashboards that are empty or have not been actively viewed in the last year.
> Maintainers: HISP Centre implementation team.
>
> **WARNING**  
> This tool is intended to be used by system administrators, not end users. It is available as a DHIS2 app, but has not been through the same rigorous testing as normal core apps. It should be used with care, and always tested in a development environment.

## License

© Copyright University of Oslo 2004-2025. Licensed under BSD-3-Clause. See LICENSE for details.

## About the app

The DHIS2 Dashboard Pruner App is a tool designed to help administrators manage and clean up
their DHIS2 dashboards by removing unused or obsolete dashboard items. This helps in maintaining
an organized and efficient dashboard environment, ensuring that only relevant and necessary items
are retained.

You can choose to remove dashboards which are empty (i.e., contain no dashboard items) or
dashboards which have not been **actively** viewed in over one year. When you delete a dashboard with this app,
the dashboard and its layout are removed, but the visualizations, maps and other content it showed are kept.

The data statistics system of DHIS2 counts two different types of views of a dashboard:

- Active views: when a user explicitly opens a dashboard in the DHIS2 dashboard app.
- Passive views: when a dashboard is loaded when the user logins to DHIS2, e.g. the default landing page dashboard.

The Dashboard Pruner App only considers active views when determining if a dashboard is stale.

If you determine that one of the dashboards which is identified by the app should not be deleted, you can
simply open the dashboard in the DHIS2 dashboard app (the **Open** link in each row) to update its last
viewed timestamp. This should have the effect of removing it from the list of dashboards identified as
stale by the integrity check used by the Dashboard Pruner App. Click **Run check again** to refresh the list.

## Requirements

- DHIS2 2.40 or newer (tested on 2.40, 2.41, 2.42 and 2.43).
- The user needs the **Perform maintenance tasks** authority (`F_PERFORM_MAINTENANCE`) or to be a
  superuser, since the app runs DHIS2's data integrity checks. Non-superusers also need the app's own
  authority (`M_DashboardPrunerTool`, shown as "DashboardPrunerTool app" in the user role editor).
- Superusers see every dashboard the check flags. Other users only see the flagged dashboards they are
  allowed to delete.

## Getting started

This is a [DHIS2 App Platform](https://developers.dhis2.org/docs/app-platform/getting-started) app, built
with [pnpm](https://pnpm.io).

### Install dependencies

```
pnpm install
```

### Start the development server

```
pnpm start --proxy https://play.im.dhis2.org/dev-2-42
```

Open http://localhost:3000 and sign in with `http://localhost:8080` as the server (the proxy) and your
DHIS2 credentials. Without `--proxy`, the dev server expects DHIS2 on http://localhost:8080; when
connecting to another instance directly, add http://localhost:3000 to its CORS allowlist.

### Build

```
pnpm build
```

This creates `build/bundle/Dashboard-Pruner-Tool-<version>.zip`, which can be installed through the
DHIS2 App Management app. Installing it upgrades earlier (0.1.x) versions of the app in place.

### Lint and test

```
pnpm lint
pnpm test
```

End-to-end tests against a live DHIS2 instance are in [`e2e/`](e2e/README.md).
