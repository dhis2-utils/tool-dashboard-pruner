import { useDataEngine } from '@dhis2/app-runtime'
import { useQuery } from '@tanstack/react-query'
import { useMemo, useRef } from 'react'
import { useFeature } from '@/hooks/useFeature'
import { DashboardProperties } from '@/lib/types'
import { FEATURES } from '@/utils/support'
import { useApiDataQuery } from '@/utils/useApiDataQuery'

type DashboardsResponse = {
    dashboards: DashboardProperties[]
}

const FIELDS =
    'id,displayName,created,lastUpdated,access[delete],sharing[public]'
const MAX_CONCURRENT_REQUESTS = 10

export const DASHBOARDS_QUERY_KEY = ['dashboards']

const isNotFound = (error: unknown) =>
    (error as { details?: { httpStatusCode?: number } })?.details
        ?.httpStatusCode === 404

const useDashboardList = () =>
    useApiDataQuery<DashboardsResponse, Error, DashboardProperties[]>({
        queryKey: [...DASHBOARDS_QUERY_KEY, 'list'],
        query: {
            resource: 'dashboards',
            params: { fields: FIELDS, paging: false },
        },
        select: (response) => response.dashboards,
        staleTime: 5 * 60 * 1000,
        cacheTime: 10 * 60 * 1000,
    })

/**
 * Fetch dashboards one by one. Up to 2.41, list queries only return
 * dashboards shared with the user, even for superusers, while a superuser
 * can still read (and delete) any dashboard by id. Missing ones (404) have
 * been deleted since the check ran.
 */
const useDashboardsById = (ids: string[]) => {
    const engine = useDataEngine()
    return useQuery<DashboardProperties[], Error>({
        queryKey: [...DASHBOARDS_QUERY_KEY, 'byId', ids],
        queryFn: async () => {
            const queue = [...ids]
            const found: DashboardProperties[] = []
            const worker = async () => {
                for (let id = queue.shift(); id; id = queue.shift()) {
                    try {
                        const response = await engine.query({
                            dashboard: {
                                resource: 'dashboards',
                                id,
                                params: { fields: FIELDS },
                            },
                        })
                        found.push(response.dashboard as DashboardProperties)
                    } catch (error) {
                        if (!isNotFound(error)) {
                            throw error
                        }
                    }
                }
            }
            await Promise.all(
                Array.from(
                    { length: Math.min(MAX_CONCURRENT_REQUESTS, ids.length) },
                    worker
                )
            )
            return found
        },
        enabled: ids.length > 0,
        keepPreviousData: true,
        staleTime: 5 * 60 * 1000,
        cacheTime: 10 * 60 * 1000,
    })
}

type UseDashboardsOptions = {
    // Dashboards the integrity check reported
    issueIds: string[] | undefined
    isSuperuser: boolean
    // A result is only kept across lookups for the same key (the check):
    // for another check it would be a misleading, partial table
    resultKey: string
}

/**
 * Metadata for the dashboards the check reported. `dashboards` is undefined
 * until every reported dashboard has been looked up once; afterwards, while
 * a new lookup for the same `resultKey` runs (`isFetching`), the last
 * complete result is kept so the table stays mounted.
 */
export const useDashboards = ({
    issueIds,
    isSuperuser,
    resultKey,
}: UseDashboardsOptions) => {
    const list = useDashboardList()
    const listIsComplete = useFeature(FEATURES.superuserListsBypassSharing)

    const missingIds = useMemo(() => {
        if (listIsComplete || !isSuperuser || !issueIds || !list.data) {
            return []
        }
        const listed = new Set(list.data.map((d) => d.id))
        return issueIds.filter((id) => !listed.has(id)).sort()
    }, [listIsComplete, isSuperuser, issueIds, list.data])

    const byId = useDashboardsById(missingIds)
    // keepPreviousData avoids flashing an empty table on refetch, but data
    // kept from other ids must not be taken as the answer for these ids
    const byIdReady =
        missingIds.length === 0 ||
        (byId.data !== undefined && !byId.isPreviousData)

    const complete = useMemo(
        () =>
            list.data && byIdReady
                ? [
                      ...list.data,
                      ...(missingIds.length ? (byId.data ?? []) : []),
                  ]
                : undefined,
        [list.data, byIdReady, missingIds.length, byId.data]
    )
    const lastComplete = useRef<{
        key: string
        dashboards: DashboardProperties[]
    }>()
    if (complete) {
        lastComplete.current = { key: resultKey, dashboards: complete }
    }
    const kept =
        lastComplete.current?.key === resultKey
            ? lastComplete.current.dashboards
            : undefined

    return {
        dashboards: complete ?? kept,
        isFetching: list.isFetching || !byIdReady || byId.isFetching,
        error: list.error ?? byId.error ?? null,
    }
}
