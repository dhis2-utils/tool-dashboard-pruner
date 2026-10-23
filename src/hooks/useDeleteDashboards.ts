import { useDataEngine } from '@dhis2/app-runtime'
import i18n from '@dhis2/d2-i18n'
import { useMutation } from '@tanstack/react-query'
import { forEachConcurrently } from '@/lib/concurrency'
import { httpStatusOf } from '@/lib/httpStatus'

const MAX_CONCURRENT_DELETES = 5

// Up to 2.42 the server answers with the raw constraint violation when a
// push analysis still uses the dashboard
const describeError = (error: unknown) => {
    const message = (error as Error)?.message ?? String(error)
    return /pushanalysis/i.test(message)
        ? i18n.t('used by a push analysis; delete the push analysis first')
        : message
}

export interface DeleteFailure {
    id: string
    message: string
}
export interface DeleteResult {
    deleted: string[]
    failed: DeleteFailure[]
}

interface UseDeleteDashboardsOptions {
    onProgress?: (done: number) => void
    onSettled?: (result: DeleteResult) => void
}

export const useDeleteDashboards = ({
    onProgress,
    onSettled,
}: UseDeleteDashboardsOptions = {}) => {
    const engine = useDataEngine()

    const deleteAll = async (ids: string[]): Promise<DeleteResult> => {
        const result: DeleteResult = { deleted: [], failed: [] }

        await forEachConcurrently(ids, MAX_CONCURRENT_DELETES, async (id) => {
            try {
                await engine.mutate({
                    resource: 'dashboards',
                    id,
                    type: 'delete',
                })
                result.deleted.push(id)
            } catch (error) {
                // Someone else deleted it since the check ran: it is gone,
                // which is what the user asked for
                if (httpStatusOf(error) === 404) {
                    result.deleted.push(id)
                } else {
                    result.failed.push({
                        id,
                        message: describeError(error),
                    })
                }
            }
            onProgress?.(result.deleted.length + result.failed.length)
        })
        return result
    }

    const { mutate, isLoading } = useMutation<DeleteResult, Error, string[]>(
        deleteAll,
        { onSuccess: onSettled }
    )

    return { deleteDashboards: mutate, isDeleting: isLoading }
}
