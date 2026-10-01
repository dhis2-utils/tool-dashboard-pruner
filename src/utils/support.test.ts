import { FEATURES, hasAPISupportForFeature } from './support'

describe('hasAPISupportForFeature', () => {
    it('superuser lists bypass sharing from 2.42', () => {
        const feature = FEATURES.superuserListsBypassSharing
        expect(hasAPISupportForFeature(41, feature)).toBe(false)
        expect(hasAPISupportForFeature('42', feature)).toBe(true)
        expect(hasAPISupportForFeature(43, feature)).toBe(true)
    })
})
