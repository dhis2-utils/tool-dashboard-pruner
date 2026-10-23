import { httpStatusOf } from './httpStatus'

describe('httpStatusOf', () => {
    it('reads the status of a data engine error', () => {
        expect(httpStatusOf({ details: { httpStatusCode: 404 } })).toBe(404)
    })

    it('returns undefined for other errors', () => {
        expect(httpStatusOf(new Error('network'))).toBeUndefined()
        expect(httpStatusOf(null)).toBeUndefined()
        expect(httpStatusOf(undefined)).toBeUndefined()
    })
})
