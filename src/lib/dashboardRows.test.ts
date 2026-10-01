import {
    buildDashboardRows,
    daysSince,
    parsePublicAccess,
} from './dashboardRows'
import { DashboardProperties } from './types'

const now = new Date('2026-10-01T12:00:00')

const dashboard = (
    id: string,
    overrides: Partial<DashboardProperties> = {}
): DashboardProperties => ({
    id,
    displayName: `Dashboard ${id}`,
    created: '2026-09-01T12:00:00.000',
    lastUpdated: '2026-09-21T12:00:00.000',
    access: { delete: true },
    sharing: { public: 'rw------' },
    ...overrides,
})

describe('daysSince', () => {
    it('parses API and integrity-SQL timestamp formats', () => {
        expect(daysSince('2026-09-21T12:00:00.000', now)).toBe(10)
        expect(daysSince('2026-09-21 11:59:59.5', now)).toBe(10)
    })

    it('returns null for missing or invalid values', () => {
        expect(daysSince(null, now)).toBeNull()
        expect(daysSince(undefined, now)).toBeNull()
        expect(daysSince('not a date', now)).toBeNull()
    })
})

describe('parsePublicAccess', () => {
    it('distinguishes edit, view and no public access', () => {
        expect(parsePublicAccess('rw------')).toBe('edit')
        expect(parsePublicAccess('r-------')).toBe('view')
        expect(parsePublicAccess('--------')).toBe('none')
        expect(parsePublicAccess(undefined)).toBeNull()
    })
})

describe('buildDashboardRows', () => {
    const issues = [
        { id: 'a', name: 'raw a', comment: '2024-09-01 12:00:00.0' },
        { id: 'b', name: 'raw b', comment: null },
        { id: 'c', name: 'raw c' },
    ]
    const dashboards = [
        dashboard('a'),
        dashboard('b', { access: { delete: false } }),
    ]

    it('lists every existing dashboard for superusers', () => {
        const rows = buildDashboardRows({
            issues,
            dashboards,
            isSuperuser: true,
            reportsLastViewed: true,
            now,
        })
        // c is not in the dashboard list: deleted since the check ran
        expect(rows.map((r) => r.id)).toEqual(['a', 'b'])
        expect(rows[0]).toMatchObject({
            name: 'Dashboard a',
            createdDaysAgo: 30,
            lastUpdatedDaysAgo: 10,
            lastViewedDaysAgo: 760,
            publicAccess: 'edit',
        })
        expect(rows[1].lastViewedDaysAgo).toBeNull()
    })

    it('lists the push analyses using a dashboard', () => {
        const rows = buildDashboardRows({
            issues,
            dashboards,
            pushAnalysesByDashboard: new Map([['a', ['Monthly report']]]),
            isSuperuser: true,
            reportsLastViewed: false,
            now,
        })
        expect(rows[0].pushAnalyses).toEqual(['Monthly report'])
        expect(rows[1].pushAnalyses).toEqual([])
    })

    it('only lists deletable dashboards for other users', () => {
        const rows = buildDashboardRows({
            issues,
            dashboards,
            isSuperuser: false,
            reportsLastViewed: false,
            now,
        })
        expect(rows.map((r) => r.id)).toEqual(['a'])
        expect(rows[0]).not.toHaveProperty('lastViewedDaysAgo')
    })
})
