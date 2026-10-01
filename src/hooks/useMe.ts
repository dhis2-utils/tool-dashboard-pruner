import { useApiDataQuery } from '@/utils/useApiDataQuery'

type Me = {
    id: string
    authorities: string[]
}

const MAINTENANCE_AUTHORITY = 'F_PERFORM_MAINTENANCE'

export const useMe = () => {
    const { data, isLoading, error } = useApiDataQuery<Me>({
        queryKey: ['me'],
        query: { resource: 'me', params: { fields: 'id,authorities' } },
        cacheTime: Infinity,
        staleTime: Infinity,
    })

    const authorities = data?.authorities ?? []
    const isSuperuser = authorities.includes('ALL')

    return {
        isSuperuser,
        // The dataIntegrity endpoints require ALL or F_PERFORM_MAINTENANCE
        canRunChecks:
            isSuperuser || authorities.includes(MAINTENANCE_AUTHORITY),
        isLoading,
        error,
    }
}
