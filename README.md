# Dashboard Pruner Tool

> ![Maturity: Experimental](https://img.shields.io/badge/maturity-Experimental-orange)  
> Intended use: find dashboards that are empty or not viewed in a year, and delete them.  
> Maintainers: HISP Centre implementation team.

> [!WARNING]
> This tool is for system administrators. It deletes dashboards, and a delete cannot be undone. Try it on a copy of your database first.

A DHIS2 app that runs the "dashboards with no items" and "dashboards not viewed in one year" data integrity checks, lists the dashboards they find, and deletes the ones you choose. How to install and use it is in the [user documentation](docs/user/tool-dashboard-pruner.md).

## Supported DHIS2 versions

2.40 and later (`minDHIS2Version` in `d2.config.js`). The e2e suite runs on 2.40, 2.41, 2.42 and 2.43.

## Prerequisites

- Node.js 22 and [pnpm](https://pnpm.io) (the version is pinned in `package.json` under `packageManager`; `corepack enable` picks it up).
- A DHIS2 instance to run against. For a local one, see [DHIS2 in Docker](https://developers.dhis2.org/docs/tutorials/dhis2-docker/).

## Install dependencies

```
pnpm install
```

## Start the app against a local instance

```
pnpm start --proxy http://localhost:8080
```

Open http://localhost:3000 and log in with `http://localhost:8080` as the server and your DHIS2 credentials. The proxy forwards the API requests, so the instance needs no CORS setting.

## Test, lint and build

```
pnpm test        # unit tests (Jest, src/**/*.test.ts)
pnpm run lint    # Ultracite: Oxlint and Oxfmt, over the DHIS2 house style
pnpm run format  # rewrite files with Oxfmt
pnpm exec tsc --noEmit
pnpm run build   # build/bundle/tool-dashboard-pruner-<version>.zip
```

Linting follows [LINTING.md](https://github.com/dhis2-utils/reference-tool-conventions/blob/main/LINTING.md) in reference-tool-conventions. A Claude Code hook (`.claude/hooks/ultracite-fix.sh`) lints each file an agent edits; nothing else depends on it.

The end-to-end suite installs the built app on a DHIS2 instance and drives it in a browser. It deletes data, so only run it against a throwaway instance: see [`e2e/README.md`](e2e/README.md).

## Release

Releases follow [RELEASE-WORKFLOW.md](https://github.com/dhis2-utils/reference-tool-conventions/blob/main/RELEASE-WORKFLOW.md) in reference-tool-conventions: bump `version` in `package.json`, add a section to `CHANGELOG.md`, merge to `main`, then push a `vX.Y.Z` tag on the merged commit. The Release workflow builds the app and attaches the zip to a GitHub release.

## License

© Copyright University of Oslo 2004-2025. Licensed under BSD-3-Clause. See [LICENSE](LICENSE) for details.
