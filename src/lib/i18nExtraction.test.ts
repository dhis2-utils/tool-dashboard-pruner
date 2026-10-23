import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'

// The DHIS2 translation extractor silently drops i18n.t keys that contain a
// colon, pass a `count` option or have a TypeScript cast in their options,
// and cuts a key that contains an underscore at the last one (it reads the
// rest as a plural or context suffix). Such a key is never translated, and
// nothing else reports it.
const SRC = path.join(__dirname, '..')
const POT = path.join(SRC, '..', 'i18n', 'en.pot')
// The first argument of i18n.t, as a single- or double-quoted literal
const KEY = /i18n\.t\(\s*(['"])((?:\\.|(?!\1).)*)\1/gs

const sourceFiles = (dir: string): string[] =>
    readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
        const full = path.join(dir, entry.name)
        if (entry.isDirectory()) {
            return entry.name === 'locales' ? [] : sourceFiles(full)
        }
        return /\.tsx?$/.test(entry.name) && !entry.name.includes('.test.')
            ? [full]
            : []
    })

const keysInSource = () =>
    sourceFiles(SRC).flatMap((file) =>
        [...readFileSync(file, 'utf8').matchAll(KEY)].map((m) =>
            m[2].replaceAll(`\\${m[1]}`, m[1])
        )
    )

// A msgid can continue over several quoted lines
const keysInPot = () =>
    new Set(
        [
            ...readFileSync(POT, 'utf8').matchAll(
                /^msgid ((?:".*"\n)(?:".*"\n)*)/gm
            ),
        ]
            .map((m) =>
                [...m[1].matchAll(/"(.*)"/g)]
                    .map((part) => part[1])
                    .join('')
                    .replaceAll('\\"', '"')
            )
            .filter(Boolean)
    )

describe('i18n extraction', () => {
    const keys = keysInSource()

    it('finds the keys in the source', () => {
        expect(keys.length).toBeGreaterThan(20)
    })

    it('has every key in i18n/en.pot', () => {
        const pot = keysInPot()
        expect(keys.filter((key) => !pot.has(key))).toEqual([])
    })

    it('has no key the extractor would drop', () => {
        expect(keys.filter((key) => /[:_]/.test(key))).toEqual([])
        const source = sourceFiles(SRC)
            .map((file) => readFileSync(file, 'utf8'))
            .join('\n')
        expect(source).not.toMatch(/i18n\.t\([^)]*\bcount\s*:/s)
        expect(source).not.toMatch(/i18n\.t\([^)]*\bas\s+[A-Z]/s)
    })
})
