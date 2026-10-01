export type IntegrityIssue = {
    id: string
    name: string
    // For dashboards_not_viewed_one_year: the last active view timestamp as
    // text, or null when the dashboard was never viewed. Unused otherwise.
    comment?: string | null
}

export type IntegrityDetails = {
    name: string
    startTime?: string
    finishedTime?: string
    error?: string
    issues: IntegrityIssue[]
}

export type DashboardProperties = {
    id: string
    displayName: string
    created: string
    lastUpdated: string
    access: { delete: boolean }
    sharing?: { public?: string }
}

export type PublicAccess = 'edit' | 'view' | 'none'

export type DashboardRow = {
    id: string
    name: string
    createdDaysAgo: number | null
    lastUpdatedDaysAgo: number | null
    // null when never viewed; undefined when the check doesn't report views
    lastViewedDaysAgo?: number | null
    publicAccess: PublicAccess | null
}
