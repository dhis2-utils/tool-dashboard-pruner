import { useDataEngine } from '@dhis2/app-runtime'
import { useMutation } from '@tanstack/react-query'

const MAX_CONCURRENT_DELETES = 5

export type DeleteFailure = { id: string; message: string }
export type DeleteResult = { deleted: string[]; failed: DeleteFailure[] }

type UseDeleteDashboardsOptions = {
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
        const queue = [...ids]

        const worker = async () => {
            for (let id = queue.shift(); id; id = queue.shift()) {
                try {
                    await engine.mutate({
                        resource: 'dashboards',
                        id,
                        type: 'delete',
                    })
                    result.deleted.push(id)
                } catch (error) {
                    result.failed.push({
                        id,
                        message: (error as Error)?.message ?? String(error),
                    })
                }
                onProgress?.(result.deleted.length + result.failed.length)
            }
        }

        await Promise.all(
            Array.from(
                { length: Math.min(MAX_CONCURRENT_DELETES, ids.length) },
                worker
            )
        )
        return result
    }

    const { mutate, isLoading } = useMutation<DeleteResult, Error, string[]>(
        deleteAll,
        { onSuccess: onSettled }
    )

    return { deleteDashboards: mutate, isDeleting: isLoading }
}
