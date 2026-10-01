import { useFeature } from '@/hooks/useFeature'
import { FEATURES } from '@/utils/support'
import { useApiDataQuery } from '@/utils/useApiDataQuery'

type PushAnalysis = {
    id: string
    displayName: string
    dashboard?: { id: string }
}

type PushAnalysesResponse = { pushAnalysis: PushAnalysis[] }

export type PushAnalysesByDashboard = Map<string, string[]>

export const PUSH_ANALYSES_QUERY_KEY = ['pushAnalyses']

const NONE: PushAnalysesByDashboard = new Map()

/**
 * Push analyses by dashboard id (up to 2.42; the feature was removed in
 * 2.43). Push analyses have no sharing, so superusers get the full list even
 * on 2.40/2.41. If one is created after loading and blocks a delete, the
 * delete error says so.
 */
export const usePushAnalyses = () => {
    const removed = useFeature(FEATURES.pushAnalysisRemoved)
    const { data, isLoading, error } = useApiDataQuery<
        PushAnalysesResponse,
        Error,
        PushAnalysesByDashboard
    >({
        queryKey: PUSH_ANALYSES_QUERY_KEY,
        query: {
            resource: 'pushAnalysis',
            params: { fields: 'id,displayName,dashboard[id]', paging: false },
        },
        select: (response) => {
            const byDashboard: PushAnalysesByDashboard = new Map()
            for (const { displayName, dashboard } of response.pushAnalysis) {
                if (dashboard) {
                    const names = byDashboard.get(dashboard.id) ?? []
                    byDashboard.set(dashboard.id, [...names, displayName])
                }
            }
            return byDashboard
        },
        enabled: !removed,
        staleTime: 5 * 60 * 1000,
        cacheTime: 10 * 60 * 1000,
    })

    return {
        pushAnalysesByDashboard: removed ? NONE : data,
        isLoading: !removed && isLoading,
        error,
    }
}
