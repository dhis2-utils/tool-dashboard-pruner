# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0]

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
- Requires DHIS2 2.40 or newer.

### Added

- "Last viewed (days ago)" column for the "not viewed in one year" check, showing "Never" for
  dashboards that were never opened.
- "Run check again" button and the time the shown results were computed.
- Public access shows whether the public can view or edit a dashboard.
- Translatable user interface.

### Fixed

- Deleted dashboards no longer reappear in the list after deleting. The server keeps the previous
  integrity check result for up to an hour and keeps serving it while a new run is in progress; the
  app now waits for the result of the run it started.
- Dashboards that are public with view-only access were shown as "Private".
- The "last updated" column showed the last viewed date for the "not viewed in one year" check.
- On DHIS2 2.40 and 2.41, dashboards not shared with the superuser showed "Unknown" for created date and
  public access. They are now looked up individually.
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
