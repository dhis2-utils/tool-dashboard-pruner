import { FEATURES, hasAPISupportForFeature } from './support'

describe('hasAPISupportForFeature', () => {
    it('superuser lists bypass sharing from 2.42', () => {
        const feature = FEATURES.superuserListsBypassSharing
        expect(hasAPISupportForFeature(41, feature)).toBe(false)
        expect(hasAPISupportForFeature('42', feature)).toBe(true)
        expect(hasAPISupportForFeature(43, feature)).toBe(true)
    })

    it('push analysis is gone from 2.43', () => {
        const feature = FEATURES.pushAnalysisRemoved
        expect(hasAPISupportForFeature(42, feature)).toBe(false)
        expect(hasAPISupportForFeature(43, feature)).toBe(true)
    })
})
