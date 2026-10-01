import { useDataEngine } from '@dhis2/app-runtime'
import i18n from '@dhis2/d2-i18n'
import { useQuery } from '@tanstack/react-query'
import { CheckCode } from '@/lib/checks'
import { IntegrityDetails } from '@/lib/types'

type DataEngine = ReturnType<typeof useDataEngine>
type DetailsResponse = Record<string, IntegrityDetails | undefined>

const DETAILS_RESOURCE = 'dataIntegrity/details'
const POLL_INTERVAL_MS = 1000
const POLL_TIMEOUT_MS = 5 * 60 * 1000
const MAX_CONSECUTIVE_POLL_ERRORS = 3

export const INTEGRITY_CHECK_QUERY_KEY = 'integrityCheck'

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

const getCachedDetails = async (engine: DataEngine, code: CheckCode) => {
    const response = await engine.query({
        details: { resource: DETAILS_RESOURCE, params: { checks: code } },
    })
    return (response.details as DetailsResponse)[code]
}

const isConflict = (error: unknown) =>
    (error as { details?: { httpStatusCode?: number } })?.details
        ?.httpStatusCode === 409

/**
 * Run an integrity check and wait for a result produced by *this* run.
 *
 * GET dataIntegrity/details only reads the server's result cache (kept for
 * an hour, never invalidated when a rerun starts), so it keeps returning the
 * previous result while the new run is in progress. Remember the previous
 * run's startTime and wait until a result with a different one appears.
 *
 * The data engine can't abort requests, so `signal` (set when react-query
 * cancels the query) only stops the polling loop.
 */
const runIntegrityCheck = async (
    engine: DataEngine,
    code: CheckCode,
    signal?: AbortSignal
): Promise<IntegrityDetails> => {
    const previousStartTime = (await getCachedDetails(engine, code))?.startTime

    try {
        await engine.mutate({
            resource: DETAILS_RESOURCE,
            type: 'create',
            data: [code],
        })
    } catch (error) {
        // 2.40 answers 409 when the check is already running. That run will
        // produce a fresh result, so just wait for it.
        if (!isConflict(error)) {
            throw error
        }
    }

    const giveUpAt = Date.now() + POLL_TIMEOUT_MS
    let pollErrors = 0
    while (Date.now() < giveUpAt && !signal?.aborted) {
        await sleep(POLL_INTERVAL_MS)
        let details: IntegrityDetails | undefined
        try {
            details = await getCachedDetails(engine, code)
            pollErrors = 0
        } catch (error) {
            // Tolerate a transient failure; the run continues server-side
            if (
                ++pollErrors >= MAX_CONSECUTIVE_POLL_ERRORS ||
                signal?.aborted
            ) {
                throw error
            }
            continue
        }
        if (details?.finishedTime && details.startTime !== previousStartTime) {
            if (details.error) {
                throw new Error(details.error)
            }
            return details
        }
    }
    throw new Error(
        i18n.t('Timed out waiting for the integrity check to finish')
    )
}

export const useIntegrityCheck = (code: CheckCode, enabled: boolean) => {
    const engine = useDataEngine()
    const { data, isFetching, error, refetch } = useQuery<
        IntegrityDetails,
        Error
    >({
        queryKey: [INTEGRITY_CHECK_QUERY_KEY, code],
        queryFn: ({ signal }) => runIntegrityCheck(engine, code, signal),
        enabled,
        // Every fetch reruns the check on the server: only do it on request,
        // or after a deletion has invalidated the result
        staleTime: Infinity,
        cacheTime: Infinity,
        retry: false,
        refetchOnWindowFocus: false,
    })

    return { details: data, isRunning: isFetching, error, rerun: refetch }
}
