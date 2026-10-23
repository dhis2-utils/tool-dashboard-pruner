/** The HTTP status of a failed data engine request, if it has one. */
export const httpStatusOf = (error: unknown) =>
    (error as { details?: { httpStatusCode?: number } } | null)?.details
        ?.httpStatusCode
