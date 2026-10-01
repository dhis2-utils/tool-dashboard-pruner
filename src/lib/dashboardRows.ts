import {
    DashboardProperties,
    DashboardRow,
    IntegrityIssue,
    PublicAccess,
} from './types'

const DAY_MS = 24 * 60 * 60 * 1000

// DHIS2 returns server-local timestamps without a zone ("2024-12-06 21:03:07.96"
// from the integrity SQL, "2024-12-06T21:03:07.960" from the metadata API).
// Day granularity makes the missing offset irrelevant.
export const daysSince = (
    timestamp: string | null | undefined,
    now: Date
): number | null => {
    if (!timestamp) {
        return null
    }
    const time = new Date(timestamp.replace(' ', 'T')).getTime()
    if (Number.isNaN(time)) {
        return null
    }
    return Math.max(0, Math.floor((now.getTime() - time) / DAY_MS))
}

export const parsePublicAccess = (
    publicSharing: string | undefined
): PublicAccess | null => {
    if (!publicSharing) {
        return null
    }
    if (publicSharing.startsWith('rw')) {
        return 'edit'
    }
    if (publicSharing.startsWith('r')) {
        return 'view'
    }
    return 'none'
}

type BuildRowsOptions = {
    issues: IntegrityIssue[]
    dashboards: DashboardProperties[]
    isSuperuser: boolean
    reportsLastViewed: boolean
    now?: Date
}

/**
 * Join integrity-check issues with the dashboards' metadata.
 *
 * Issues without a matching dashboard are dropped: the check result can be
 * older than the dashboard list (the server caches it, and the app keeps it
 * while a rerun is in progress), so these are dashboards deleted since. For
 * superusers the list holds every dashboard; other users only see dashboards
 * they can delete, as the check itself ignores sharing.
 */
export const buildDashboardRows = ({
    issues,
    dashboards,
    isSuperuser,
    reportsLastViewed,
    now = new Date(),
}: BuildRowsOptions): DashboardRow[] => {
    const byId = new Map(dashboards.map((d) => [d.id, d]))

    return issues.flatMap((issue) => {
        const dashboard = byId.get(issue.id)
        if (!dashboard || !(isSuperuser || dashboard.access.delete)) {
            return []
        }
        return [
            {
                id: issue.id,
                name: dashboard.displayName,
                createdDaysAgo: daysSince(dashboard.created, now),
                lastUpdatedDaysAgo: daysSince(dashboard.lastUpdated, now),
                ...(reportsLastViewed && {
                    lastViewedDaysAgo: daysSince(issue.comment, now),
                }),
                publicAccess: parsePublicAccess(dashboard.sharing?.public),
            },
        ]
    })
}
