# Changelog

All notable changes to this project will be documented in this file.

## [1.1.0]

### Upgrading

- The app key changes from `Dashboard-Pruner-Tool` to `tool-dashboard-pruner`, to match the repository name. DHIS2 treats this version as a different app, so:
    - Install this version, then uninstall the old Dashboard Pruner Tool in App Management, or two entries remain in the menu.
    - Add the new app to every user role that gave access to the old one. Until then, users without the ALL authority cannot open it. The app authority is now `M_tooldashboardpruner`.
    - Bookmarks to the old app URL stop working.

### Added

- User documentation in `docs/user/`.

### Changed

- Lint and format with Ultracite on Oxlint and Oxfmt, over the DHIS2 house style, instead of ESLint and Prettier.
- The e2e suite follows the `e2e/run.sh` contract of reference-tool-conventions: it installs the app, gives everything it creates a run-unique name, records it in the dataStore, and deletes it afterwards. It also covers cancel, **Run check again**, a dashboard deleted by someone else, and a dashboard name with HTML in it.
- CI and release workflows match the reference-tool-conventions templates. The release job no longer restores a dependency cache, and a re-run uploads to an existing release instead of failing.

### Fixed

- Deleting a dashboard that someone else deleted after the check ran reported "An unknown error occurred - (404)" and kept it selected. It now counts as deleted.
- The table remounted every cell whenever a refresh started or finished.
- The "Missing authority" message could not be translated: the translation extractor cut its key at the underscore in `F_PERFORM_MAINTENANCE`. A unit test now checks that every key reaches `i18n/en.pot` whole.

## [1.0.0]

### Upgrading

- Requires DHIS2 2.40 or later.

### Added

- Dashboards that a push analysis uses (up to DHIS2 2.42) are marked and cannot be selected or deleted,
  since the server refuses to delete them. If a delete still fails for that reason, the message says so
  instead of showing the database error.
- "Last viewed (days ago)" column for the "not viewed in one year" check, showing "Never" for
  dashboards that were never opened.
- "Run check again" button and the time the shown results were computed.
- Public access shows whether the public can view or edit a dashboard.
- Translatable user interface.

### Changed

- Rebuilt on the DHIS2 App Platform (React, `@dhis2/ui`, `@dhis2/app-runtime`), replacing the
  webpack/jQuery/DataTables implementation. The app key is unchanged, so installing this version
  upgrades 0.1.x in place.
- One selection checkbox per row plus a select-all checkbox (which selects only the rows matching the
  current search) replace the separate "Delete selected" / "Delete all empty dashboards" buttons.
- Deletions are confirmed in a dialog that lists the dashboards to be deleted.
- The "Share with me" button and the automatic sharing of each dashboard before deleting it were
  removed: superusers can already read and delete every dashboard, and other users are only shown
  dashboards they can delete. Each row has an **Open** link to the dashboard instead.

### Fixed

- Deleted dashboards no longer reappear in the list after deleting. The server keeps the previous
  integrity check result for up to an hour and keeps serving it while a new run is in progress; the
  app now waits for the result of the run it started.
- Dashboards that are public with view-only access were shown as "Private".
- The "last updated" column showed the last viewed date for the "not viewed in one year" check.
- On DHIS2 2.40 and 2.41, dashboards not shared with the superuser showed "Unknown" for created date and
  public access. They are now looked up individually.

### Security

- Dashboard names are no longer inserted into the page as HTML (stored cross-site scripting).

## [0.1.1]

### Added

- Include DHIS2 header bar

### Fixed

- Fixed webpack config to properly load project

## [0.1.0]

### Added

- Initial release.
- Updated automation to release zip artifact.
