export const FEATURES = Object.freeze({
    // List queries return every dashboard to superusers, regardless of sharing
    superuserListsBypassSharing: 'superuserListsBypassSharing',
})

const MINOR_VERSION_SUPPORT: Record<string, number> = Object.freeze({
    [FEATURES.superuserListsBypassSharing]: 42,
})

export const hasAPISupportForFeature = (
    minorVersion: string | number,
    featureName: string
) => MINOR_VERSION_SUPPORT[featureName] <= Number(minorVersion) || false
