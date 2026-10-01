import i18n from '@dhis2/d2-i18n'

export const CHECK_NO_ITEMS = 'dashboards_no_items'
export const CHECK_NOT_VIEWED = 'dashboards_not_viewed_one_year'

export type CheckCode = typeof CHECK_NO_ITEMS | typeof CHECK_NOT_VIEWED

const CHECK_CODES: CheckCode[] = [CHECK_NO_ITEMS, CHECK_NOT_VIEWED]

// A function, not a constant: labels must be translated at render time,
// after the app's locales have been loaded
export const getChecks = (): { code: CheckCode; label: string }[] => [
    { code: CHECK_NO_ITEMS, label: i18n.t('Dashboards with no items') },
    {
        code: CHECK_NOT_VIEWED,
        label: i18n.t('Dashboards not viewed in one year'),
    },
]

export const isCheckCode = (value: string | null): value is CheckCode =>
    CHECK_CODES.includes(value as CheckCode)
