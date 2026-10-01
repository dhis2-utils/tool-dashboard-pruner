export const FEATURES = Object.freeze({
    // List queries return every dashboard to superusers, regardless of sharing
    superuserListsBypassSharing: 'superuserListsBypassSharing',
    // Push analysis (which blocks deleting its dashboard) was removed in 2.43
    pushAnalysisRemoved: 'pushAnalysisRemoved',
})

const MINOR_VERSION_SUPPORT: Record<string, number> = Object.freeze({
    [FEATURES.superuserListsBypassSharing]: 42,
    [FEATURES.pushAnalysisRemoved]: 43,
})

export const hasAPISupportForFeature = (
    minorVersion: string | number,
    featureName: string
) => MINOR_VERSION_SUPPORT[featureName] <= Number(minorVersion) || false
