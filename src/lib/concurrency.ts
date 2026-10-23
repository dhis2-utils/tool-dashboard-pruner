/**
 * Run `task` for every item, at most `limit` at a time. Resolves when every
 * task has finished; rejects with the first error a task throws, so tasks
 * that should not stop the others must handle their own errors.
 */
export const forEachConcurrently = async <T>(
    items: readonly T[],
    limit: number,
    task: (item: T) => Promise<void>
) => {
    const queue = [...items]
    const worker = async () => {
        for (
            let item = queue.shift();
            item !== undefined;
            item = queue.shift()
        ) {
            // oxlint-disable-next-line no-await-in-loop -- each worker takes one item at a time; `limit` workers run side by side
            await task(item)
        }
    }
    await Promise.all(
        Array.from({ length: Math.min(limit, items.length) }, worker)
    )
}
