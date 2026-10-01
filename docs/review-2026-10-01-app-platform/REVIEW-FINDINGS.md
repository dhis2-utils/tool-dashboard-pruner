# Review findings: Dashboard Pruner Tool v0.2.0 (App Platform migration)

Reviewed: 2026-10-01 · Scope: code review + functional test (multi-version), after migrating from the
webpack/jQuery tool to the App Platform · Reviewer: agent (Claude Code, Opus 5.5, plus an independent
second-opinion review subagent whose claims were verified before inclusion)
DHIS2 versions tested: 2.40.12 (Sierra Leone), 2.41.10 (Lao HMIS), 2.42.6 (Sierra Leone), 2.43.1 (Lao HMIS)

## Summary

The migrated app passes the full acceptance suite on all four versions. The suite covers 9 flows, including
deletes checked against server state, and it asserts there are no app console or network errors. All
HIGH and MEDIUM issues found during review are fixed: see [FIXES.md](FIXES.md).

The legacy 0.1.x app has two serious defects, both reproduced live:

- **Stored XSS.** Any user who can create a dashboard can run script in the administrator's session.
- **Deleted dashboards come back.** After a delete, the list shows the deleted dashboards again.

Both are gone in 0.2.0. That alone is a reason to ship this version. 0.2.0 keeps the old app key, so it
upgrades installed 0.1.x copies in place.

Open items are LOW only.

## Findings in the legacy 0.1.9 app (fixed by the migration)

### HIGH

#### H1. Stored XSS through dashboard names

- **Where**: `src/app.js:109` and `:141` (0.1.9). The table HTML is built from `issue.name` without escaping
  and then assigned to `innerHTML`.
- **What**: a dashboard named `<img src=x onerror=…>` runs script in the session of whoever opens the
  pruner, typically a superuser. On 2.43 Lao, a non-superuser (`pruner_tester`) created such a dashboard,
  and the script ran when `local_admin` opened 0.1.9.
- **Fix**: done in 0.2.0. React renders the name as text, which was verified live on the same instance.

#### H2. Deleted dashboards reappear after deleting

- **Where**: `src/js/d2api.js:170` (`performPostAndGet`), called from `src/app.js:137` (0.1.9).
- **What**: `GET /api/dataIntegrity/details` only reads a server-side result cache. The cache is kept
  for one hour and is not cleared when a rerun starts (`DefaultDataIntegrityService.getCached` /
  `runDataIntegrityChecks`, 2.40.12 and 2.43.1). The legacy app POSTs a rerun and immediately GETs, so
  it receives the previous result.
- **Effect**: live on 2.42, the deleted dashboard was still listed after the "Dashboard deleted" alert.
  Deleting it again fails with a 404.
- **Fix**: done in 0.2.0. The app records the cached run's `startTime` before POSTing, then polls until a
  result with a different `startTime` appears (`src/hooks/useIntegrityCheck.ts`).

### MEDIUM

#### M1. "Delete all empty dashboards" is mislabelled and covers only the visible page

- **Where**: `src/app.js:123,233-236` (0.1.9).
- **What**: the button is shown for both checks. On "not viewed in one year" it deletes stale
  dashboards that are not empty. It ticks the `.dashboard-select` checkboxes, but DataTables only keeps
  the current page's rows in the DOM, so the delete covers the first page only. (Found by code reading;
  not reproduced live.)
- **Fix**: done in 0.2.0. A select-all checkbox selects exactly the rows matching the search, and a
  confirmation dialog lists them.

#### M2. View-only public dashboards shown as "Private"

- **Where**: `src/app.js:98` (0.1.9): `sharing.public.startsWith("rw")`.
- **Fix**: done in 0.2.0, which shows "Public (can view)", "Public (can edit)" and "Not public".

### LOW

#### L1. Share-before-delete is redundant and pollutes sharing — `src/app.js:247-256` (0.1.9)

Before every delete, the app appends the current user to the dashboard's `userAccesses`, without checking
whether the user is already there. That is a pointless write.

This was verified live on 2.40, 2.41, 2.42 and 2.43:

- A superuser gets `read/update/delete/manage = true` on a private dashboard that another user owns and
  shares with no one. Every version also deleted four such dashboards through the UI.
- Non-superusers only see rows they can already delete.

Removed in 0.2.0, together with the "Share with me" button, which had the same no-op effect.

#### L2. "Last updated" column showed the last-viewed date for the not-viewed check — `src/app.js:75-83` (0.1.9)

The integrity SQL's `comment` is the last-view timestamp. 0.2.0 shows it in a separate "Last viewed" column,
with "Never" for dashboards that were never viewed.

### Found during the multi-version pass (fixed in 0.2.0)

#### M3. Up to 2.41, superusers' dashboard lists leave out dashboards not shared with them

- **Where**: `src/hooks/useDashboards.ts`
- **What**: the integrity check sees every dashboard, but up to 2.41 the dashboards list a superuser gets
  back is filtered by sharing. On the Lao demo that is 3 of 198 dashboards. Two versions of the app were
  affected:
    - The legacy app and the first 0.2.0 build showed the missing rows with "Unknown" for created and public
      access. The first matrix pass did not assert those columns.
    - After the H1 fix in FIXES.md (#1), which drops rows without a matching dashboard, those rows vanished
      entirely on 2.40 and 2.41. The rerun caught that: 2 of 6 empty dashboards were shown.
- **Fix**: done. On ≤2.41, superusers look up the missing dashboards by id, 10 at a time, and a 404 means
  "deleted". This is gated by `FEATURES.superuserListsBypassSharing` (`src/utils/support.ts`), so 2.42+
  makes no extra requests. The cost on the Lao 2.41 database is about 170 small GETs per check.

#### M4. Deleting a dashboard used by a push analysis fails with a database error (up to 2.42)

- **Where**: `src/hooks/usePushAnalyses.ts`, `src/components/DashboardTable.tsx`
- **What**: found in manual testing on 2.42. A bulk delete reported "22 deleted and 1 failed". The failure
  message was the raw SQL error: `violates foreign key constraint … on table "pushanalysis"`. Push analysis
  is the only table that references `dashboard` without cascading (`dashboard_items` rows are deleted with
  the dashboard). The feature, and its table, was removed in 2.43 (`V2_43_38__Remove_push_analysis_feature.sql`).
- **Fix**: done.
    - On ≤2.42 the app loads `/api/pushAnalysis`. A dashboard one uses shows "Used by push analysis …
      Delete the push analysis first.", and its checkbox and Delete button are disabled. Select-all skips it.
    - Unlike dashboards, push analyses have no sharing. The superuser got the complete list on 2.40 (2 of 2)
      and on 2.41 (1 of 1). A push analysis created after the list was loaded can still block a delete; the
      failure then reads "used by a push analysis; delete the push analysis first".
    - This is gated by `FEATURES.pushAnalysisRemoved`.

## Findings in the migrated app (0.2.0) that are still open

### LOW

#### L3. The release workflow does not lint or test — `.github/workflows/release.yml`

It builds and publishes whatever the tag points at. CI on `main` covers lint and tests, so this only matters
when a tag is pushed on an untested commit. Fix: add the `pnpm lint` / `pnpm test` steps from `ci.yml`.

#### L4. The polling logic has no unit test — `src/hooks/useIntegrityCheck.ts`

The run-and-wait logic is the most important code in the app. Today only the e2e suite exercises it,
against real servers. Suggested unit test: mock the data engine so it returns the old cached result
twice, then a new `startTime`, and assert the resolved value. Also cover the 409 and error paths.

#### L5. Select-all spans all pages — `src/components/DashboardTable.tsx` (select column)

This is intended: it selects every row matching the search, not only the 50 rows on screen. The button
shows the count and the dialog lists the names (the first 10, then "…and N more"). Worth stating in the
dialog if users find it surprising.

#### L6. e2e `total()` parses the English pagination summary — `e2e/test_pruner.py`

It only matters if the suite runs with a non-English UI locale.

## Claims investigated and rejected

- **Claim**: superusers can only read and delete other users' private dashboards on 2.42+, so
  share-before-delete may still be needed on older versions.
    - **Source**: maintainer question during this review.
    - **Partly confirmed**: deleting does not need sharing on any version, but on 2.40 and 2.41 superusers
      do not see these dashboards in _list_ queries. That became finding M3 above.
    - **Evidence for delete and read by id**: the live probe in `e2e/seed.py` (`superuser_on_foreign_private`)
      returned 200 with full access on 2.40.12, 2.41.10, 2.42.6 and 2.43.1, and the UI deleted the
      dashboards on every version.
    - **Evidence for lists**: on 2.41.10 Lao, `/api/dashboards?paging=false` returned 3 of the 198
      dashboards in the database. `id:in:[…]` filters and `/api/metadata` returned the same filtered set.
      On 2.43.1 the list returned all 194.
- **Claim**: polling could time out if the server caches a result before a run finishes.
    - **Source**: review subagent, marked as suspected.
    - **Refuted by**: `runDataIntegrityChecks` only calls `cache.put` after a check completes or fails
      (2.40.12 and 2.43.1). The `running` set is tracked separately.
- **Claim**: the Open link (`/dhis-web-dashboard/#/<id>`) may lose the hash through the 2.42+ redirect.
    - **Source**: review subagent, marked as suspected.
    - **Refuted by**: on 2.43.1 it lands on `/apps/dashboard#/<id>` and shows the right dashboard.
- **Claim**: plurals should use i18next `count` instead of branching on `=== 1`.
    - **Source**: review subagent.
    - **Rejected**: the `@dhis2/d2-i18n` / i18next build resolved by the platform ignores
      `defaultValue_plural` and renders the singular. Branching on the count is the documented convention
      for DHIS2 apps.
- **Claim**: `src/interfaces/apiQueryTypes.ts` duplicates app-runtime types.
    - **Source**: review subagent.
    - **Rejected**: it is part of the standard project recipe (`useApiDataQuery`) and is kept for
      consistency with other DHIS2 apps.

## Architecture assessment

The migration to the App Platform is the right call, and it was done. Grounding from this review:

- Both HIGH defects came from the hand-rolled layer: HTML string templating and fetch/poll code.
- The new app gets `@dhis2/ui` consistency, translations, the header bar and global shell on every
  version, and in-place upgrade from 0.1.x.
- The source is small: about 600 lines of TypeScript across 10 files.

## Environment gaps

- The `dhis2docs` MCP server was unreachable during the session. API contracts were read from the
  `dhis2-core` source instead (tags 2.40.12 and 2.43.1).
- Laos was tested on 2.41 and 2.43, and Sierra Leone on 2.40 and 2.42. There is no Laos seed for 2.40, and
  Laos on 2.42 was not run.
