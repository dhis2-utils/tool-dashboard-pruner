import { forEachConcurrently } from './concurrency'

const tick = () =>
    new Promise((resolve) => {
        setTimeout(resolve, 0)
    })

describe('forEachConcurrently', () => {
    it('runs every item, never more than the limit at a time', async () => {
        let running = 0
        let maxRunning = 0
        const done: number[] = []
        await forEachConcurrently([1, 2, 3, 4, 5, 6, 7], 3, async (item) => {
            running += 1
            maxRunning = Math.max(maxRunning, running)
            await tick()
            done.push(item)
            running -= 1
        })
        expect(done.sort()).toEqual([1, 2, 3, 4, 5, 6, 7])
        expect(maxRunning).toBe(3)
    })

    it('handles an empty list and falsy items', async () => {
        const seen: string[] = []
        await forEachConcurrently([], 5, async () => {
            await tick()
            throw new Error('not called')
        })
        await forEachConcurrently(['', 'a'], 5, async (item) => {
            await tick()
            seen.push(item)
        })
        expect(seen.sort()).toEqual(['', 'a'])
    })

    it('rejects with the error a task throws', async () => {
        await expect(
            forEachConcurrently(['a'], 1, async () => {
                await tick()
                throw new Error('boom')
            })
        ).rejects.toThrow('boom')
    })
})
