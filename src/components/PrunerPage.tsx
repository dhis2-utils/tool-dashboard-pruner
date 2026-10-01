import i18n from '@dhis2/d2-i18n'
import {
    Button,
    CircularLoader,
    NoticeBox,
    SingleSelectField,
    SingleSelectOption,
} from '@dhis2/ui'
import { useQueryClient } from '@tanstack/react-query'
import React, { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import styles from './PrunerPage.module.css'
import { DashboardTable } from '@/components/DashboardTable'
import { DASHBOARDS_QUERY_KEY, useDashboards } from '@/hooks/useDashboards'
import { useIntegrityCheck } from '@/hooks/useIntegrityCheck'
import { useMe } from '@/hooks/useMe'
import {
    PUSH_ANALYSES_QUERY_KEY,
    usePushAnalyses,
} from '@/hooks/usePushAnalyses'
import {
    CHECK_NO_ITEMS,
    CHECK_NOT_VIEWED,
    getChecks,
    isCheckCode,
} from '@/lib/checks'
import { buildDashboardRows } from '@/lib/dashboardRows'

const CHECK_PARAM = 'check'

const useSelectedCheck = () => {
    const [searchParams, setSearchParams] = useSearchParams()
    const param = searchParams.get(CHECK_PARAM)
    const check = isCheckCode(param) ? param : CHECK_NO_ITEMS
    const setCheck = (code: string) =>
        setSearchParams({ [CHECK_PARAM]: code }, { replace: true })
    return [check, setCheck] as const
}

const Loading = ({ label }: { label: string }) => (
    <div className={styles.loadingContainer}>
        <CircularLoader />
        <span>{label}</span>
    </div>
)

const ErrorNotice = ({ title, error }: { title: string; error: Error }) => (
    <div className={styles.notice}>
        <NoticeBox error title={title}>
            {error.message || i18n.t('An unknown error occurred')}
        </NoticeBox>
    </div>
)

export const PrunerPage = () => {
    const queryClient = useQueryClient()
    const [check, setCheck] = useSelectedCheck()
    const me = useMe()
    const {
        details,
        isRunning,
        error: checkError,
        rerun,
    } = useIntegrityCheck(check, me.canRunChecks)
    const issueIds = useMemo(
        () => details?.issues.map((issue) => issue.id),
        [details]
    )
    const {
        dashboards,
        isFetching: dashboardsFetching,
        error: dashboardsError,
    } = useDashboards({
        issueIds,
        isSuperuser: me.isSuperuser,
        resultKey: check,
    })

    const { pushAnalysesByDashboard, error: pushAnalysesError } =
        usePushAnalyses()

    const rows = useMemo(
        () =>
            details && dashboards
                ? buildDashboardRows({
                      issues: details.issues,
                      dashboards,
                      pushAnalysesByDashboard,
                      isSuperuser: me.isSuperuser,
                      reportsLastViewed: check === CHECK_NOT_VIEWED,
                  })
                : [],
        [details, dashboards, pushAnalysesByDashboard, me.isSuperuser, check]
    )

    const runAgain = () => {
        // Pick up dashboards created or changed since the list was loaded
        queryClient.invalidateQueries({ queryKey: DASHBOARDS_QUERY_KEY })
        queryClient.invalidateQueries({ queryKey: PUSH_ANALYSES_QUERY_KEY })
        rerun()
    }

    const renderResults = () => {
        if (me.isLoading) {
            return <Loading label={i18n.t('Loading user…')} />
        }
        if (me.error) {
            return (
                <ErrorNotice
                    title={i18n.t('Could not load the current user')}
                    error={me.error}
                />
            )
        }
        if (!me.canRunChecks) {
            return (
                <NoticeBox warning title={i18n.t('Missing authority')}>
                    {i18n.t(
                        'Running data integrity checks requires the "Perform maintenance tasks" authority (F_PERFORM_MAINTENANCE).'
                    )}
                </NoticeBox>
            )
        }
        // A failed background refetch keeps the previous data: only give up
        // on the table when there is nothing to show
        if (dashboardsError && !dashboards) {
            return (
                <ErrorNotice
                    title={i18n.t('Could not load dashboards')}
                    error={dashboardsError}
                />
            )
        }
        const failedRun = checkError && !isRunning && (
            <ErrorNotice
                title={i18n.t('The integrity check failed')}
                error={checkError}
            />
        )
        if (pushAnalysesError && !pushAnalysesByDashboard) {
            return (
                <ErrorNotice
                    title={i18n.t('Could not load push analyses')}
                    error={pushAnalysesError}
                />
            )
        }
        if (!details || !dashboards || !pushAnalysesByDashboard) {
            return (
                failedRun || (
                    <Loading label={i18n.t('Running integrity check…')} />
                )
            )
        }
        return (
            <>
                {failedRun}
                <DashboardTable
                    key={check}
                    rows={rows}
                    check={check}
                    isRefreshing={isRunning || dashboardsFetching}
                    onDeleted={() => rerun()}
                />
            </>
        )
    }

    return (
        <div className={styles.page}>
            <h1 className={styles.title}>{i18n.t('Dashboard pruner')}</h1>
            <div className={styles.notice}>
                <NoticeBox
                    warning
                    title={i18n.t('Deleting dashboards cannot be undone')}
                >
                    {i18n.t(
                        'Deleting a dashboard removes the dashboard and its layout. The visualizations, maps and other content it showed are kept. Test in a development environment first.'
                    )}
                </NoticeBox>
            </div>
            {!me.isLoading && !me.isSuperuser && me.canRunChecks && (
                <div className={styles.notice}>
                    <NoticeBox
                        title={i18n.t('Limited to dashboards you can delete')}
                    >
                        {i18n.t(
                            'You are not a superuser, so only dashboards that are shared with you with edit access are listed.'
                        )}
                    </NoticeBox>
                </div>
            )}
            <div className={styles.controls}>
                <div className={styles.checkSelect}>
                    <SingleSelectField
                        label={i18n.t('Integrity check')}
                        selected={check}
                        onChange={({ selected }) => setCheck(selected)}
                        disabled={isRunning}
                        dataTest="check-select"
                    >
                        {getChecks().map(({ code, label }) => (
                            <SingleSelectOption
                                key={code}
                                value={code}
                                label={label}
                            />
                        ))}
                    </SingleSelectField>
                </div>
                <Button
                    onClick={runAgain}
                    loading={isRunning}
                    disabled={isRunning || !me.canRunChecks}
                    dataTest="rerun-check"
                >
                    {i18n.t('Run check again')}
                </Button>
                {details?.finishedTime && !isRunning && (
                    <span className={styles.runInfo}>
                        {i18n.t('Checked at {{time}}', {
                            time: new Date(
                                details.finishedTime
                            ).toLocaleString(),
                            // React escapes; i18next would HTML-encode "/"
                            interpolation: { escapeValue: false },
                        })}
                    </span>
                )}
            </div>
            {renderResults()}
        </div>
    )
}
