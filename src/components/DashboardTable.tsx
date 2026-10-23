import { useAlert, useConfig } from '@dhis2/app-runtime'
import i18n from '@dhis2/d2-i18n'
import {
    Button,
    Checkbox,
    CircularLoader,
    DataTable,
    DataTableBody,
    DataTableCell,
    DataTableColumnHeader,
    DataTableFoot,
    DataTableHead,
    DataTableRow,
    Input,
    Pagination,
} from '@dhis2/ui'
import { useQueryClient } from '@tanstack/react-query'
import type {
    CellContext,
    Column,
    HeaderContext,
    RowData,
    RowSelectionState,
    SortingState,
    Table,
} from '@tanstack/react-table'
import {
    createColumnHelper,
    flexRender,
    getCoreRowModel,
    getFilteredRowModel,
    getPaginationRowModel,
    getSortedRowModel,
    useReactTable,
} from '@tanstack/react-table'
import React, { useMemo, useState } from 'react'
import styles from './DashboardTable.module.css'
import { DeleteDashboardsModal } from '@/components/DeleteDashboardsModal'
import { DASHBOARDS_QUERY_KEY } from '@/hooks/useDashboards'
import type { DeleteResult } from '@/hooks/useDeleteDashboards'
import { INTEGRITY_CHECK_QUERY_KEY } from '@/hooks/useIntegrityCheck'
import type { CheckCode } from '@/lib/checks'
import { CHECK_NOT_VIEWED } from '@/lib/checks'
import type { DashboardRow, PublicAccess } from '@/lib/types'

const PAGE_SIZE = 50

const publicAccessLabel = (access: PublicAccess | null) => {
    switch (access) {
        case 'edit':
            return i18n.t('Public (can edit)')
        case 'view':
            return i18n.t('Public (can view)')
        case 'none':
            return i18n.t('Not public')
        default:
            return i18n.t('Unknown')
    }
}

const daysCell = (days: number | null | undefined, emptyLabel: string) =>
    days === null || days === undefined ? (
        <span className={styles.muted}>{emptyLabel}</span>
    ) : (
        days
    )

// Sort missing values ("never viewed", "unknown") as the oldest
const daysSortingFn = (
    a: { getValue: (id: string) => unknown },
    b: { getValue: (id: string) => unknown },
    columnId: string
) => {
    const av = (a.getValue(columnId) as number | null) ?? Infinity
    const bv = (b.getValue(columnId) as number | null) ?? Infinity
    return av === bv ? 0 : av < bv ? -1 : 1
}

// What the cells need from the component that renders the table
declare module '@tanstack/react-table' {
    interface TableMeta<TData extends RowData> {
        isRefreshing: boolean
        dashboardUrl: (id: string) => string
        requestDelete: (ids: string[]) => void
    }
}

const getMeta = (table: Table<DashboardRow>) => {
    const { meta } = table.options
    if (!meta) {
        throw new Error('DashboardTable: table meta is missing')
    }
    return meta
}

const SelectAllHeader = ({ table }: HeaderContext<DashboardRow, unknown>) => {
    const { isRefreshing } = getMeta(table)
    // Rows blocked by a push analysis cannot be selected
    const filtered = table
        .getFilteredRowModel()
        .rows.filter((r) => r.getCanSelect())
    const selectedCount = filtered.filter((r) => r.getIsSelected()).length
    return (
        <Checkbox
            dense
            dataTest="select-all"
            disabled={isRefreshing || filtered.length === 0}
            label={
                <span className={styles.srOnly}>
                    {i18n.t('Select all dashboards matching the search')}
                </span>
            }
            checked={filtered.length > 0 && selectedCount === filtered.length}
            indeterminate={selectedCount > 0 && selectedCount < filtered.length}
            onChange={({ checked }) =>
                table.setRowSelection(
                    checked
                        ? Object.fromEntries(filtered.map((r) => [r.id, true]))
                        : {}
                )
            }
        />
    )
}

const SelectRowCell = ({ row, table }: CellContext<DashboardRow, unknown>) => (
    <Checkbox
        dense
        dataTest="select-row"
        disabled={getMeta(table).isRefreshing || !row.getCanSelect()}
        label={
            <span className={styles.srOnly}>
                {i18n.t('Select {{name}}', {
                    name: row.original.name,
                    interpolation: { escapeValue: false },
                })}
            </span>
        }
        checked={row.getIsSelected()}
        onChange={({ checked }) => row.toggleSelected(checked)}
    />
)

const NameCell = ({ row }: CellContext<DashboardRow, string>) => (
    <>
        {row.original.name}
        {row.original.pushAnalyses.length > 0 && (
            <div className={styles.blocked} data-test="push-analysis-note">
                {i18n.t(
                    'Used by push analysis {{names}}. Delete the push analysis first.',
                    {
                        names: row.original.pushAnalyses.join(', '),
                        interpolation: { escapeValue: false },
                    }
                )}
            </div>
        )}
    </>
)

const ActionsCell = ({ row, table }: CellContext<DashboardRow, unknown>) => {
    const { isRefreshing, dashboardUrl, requestDelete } = getMeta(table)
    return (
        <div className={styles.actions}>
            <a
                href={dashboardUrl(row.original.id)}
                target="_blank"
                rel="noreferrer"
                aria-label={i18n.t('Open {{name}} in the Dashboard app', {
                    name: row.original.name,
                    interpolation: { escapeValue: false },
                })}
            >
                {i18n.t('Open')}
            </a>
            <Button
                small
                secondary
                dataTest="delete-row"
                disabled={isRefreshing || row.original.pushAnalyses.length > 0}
                aria-label={i18n.t('Delete {{name}}', {
                    name: row.original.name,
                    interpolation: { escapeValue: false },
                })}
                onClick={() => requestDelete([row.original.id])}
            >
                {i18n.t('Delete')}
            </Button>
        </div>
    )
}

const columnHelper = createColumnHelper<DashboardRow>()

// Cells are components defined once, here: defining them inside
// DashboardTable would remount every cell whenever a refresh starts or ends
const buildColumns = (check: CheckCode) => [
    columnHelper.display({
        id: 'select',
        header: SelectAllHeader,
        cell: SelectRowCell,
    }),
    columnHelper.accessor('name', {
        header: i18n.t('Dashboard'),
        cell: NameCell,
    }),
    columnHelper.accessor('createdDaysAgo', {
        header: i18n.t('Created (days ago)'),
        cell: (info) => daysCell(info.getValue(), i18n.t('Unknown')),
        sortingFn: daysSortingFn,
        enableGlobalFilter: false,
    }),
    columnHelper.accessor('lastUpdatedDaysAgo', {
        header: i18n.t('Last updated (days ago)'),
        cell: (info) => daysCell(info.getValue(), i18n.t('Unknown')),
        sortingFn: daysSortingFn,
        enableGlobalFilter: false,
    }),
    ...(check === CHECK_NOT_VIEWED
        ? [
              columnHelper.accessor('lastViewedDaysAgo', {
                  header: i18n.t('Last viewed (days ago)'),
                  cell: (info) => daysCell(info.getValue(), i18n.t('Never')),
                  sortingFn: daysSortingFn,
                  enableGlobalFilter: false,
              }),
          ]
        : []),
    columnHelper.accessor('publicAccess', {
        header: i18n.t('Public access'),
        cell: (info) => publicAccessLabel(info.getValue()),
        enableGlobalFilter: false,
    }),
    columnHelper.display({
        id: 'actions',
        header: i18n.t('Actions'),
        cell: ActionsCell,
    }),
]

const useDashboardUrl = () => {
    const { baseUrl } = useConfig()
    return useMemo(() => {
        const root = new URL(baseUrl, window.location.href).href.replace(
            /\/?$/,
            '/'
        )
        return (id: string) => `${root}dhis-web-dashboard/#/${id}`
    }, [baseUrl])
}

const getSortDirection = (column: Column<DashboardRow>) =>
    column.getIsSorted() || 'default'

interface DashboardTableProps {
    rows: DashboardRow[]
    check: CheckCode
    isRefreshing: boolean
    onDeleted: () => void
}

export const DashboardTable = ({
    rows,
    check,
    isRefreshing,
    onDeleted,
}: DashboardTableProps) => {
    const queryClient = useQueryClient()
    const dashboardUrl = useDashboardUrl()
    const [sorting, setSorting] = useState<SortingState>([
        {
            id:
                check === CHECK_NOT_VIEWED
                    ? 'lastViewedDaysAgo'
                    : 'createdDaysAgo',
            desc: true,
        },
    ])
    const [globalFilter, setGlobalFilter] = useState('')
    const [rowSelection, setRowSelection] = useState<RowSelectionState>({})
    // Never keep rows selected that the search hides: they would be deleted
    // along with the visible ones
    const changeSearch = (value: string) => {
        setGlobalFilter(value)
        setRowSelection({})
    }
    const [pendingDelete, setPendingDelete] = useState<string[] | null>(null)

    const { show: showAlert } = useAlert(
        ({ message }: { message: string }) => message,
        ({ critical }: { critical?: boolean }) =>
            critical ? { critical: true } : { success: true }
    )

    const columns = useMemo(() => buildColumns(check), [check])

    // oxlint-disable-next-line react/incompatible-library -- this app is not built with the React Compiler, the only thing the rule protects
    const table = useReactTable({
        data: rows,
        columns,
        state: { sorting, globalFilter, rowSelection },
        initialState: { pagination: { pageIndex: 0, pageSize: PAGE_SIZE } },
        getRowId: (row) => row.id,
        enableRowSelection: (row) => row.original.pushAnalyses.length === 0,
        onSortingChange: setSorting,
        meta: { isRefreshing, dashboardUrl, requestDelete: setPendingDelete },
        onGlobalFilterChange: (updater) =>
            changeSearch(
                typeof updater === 'function' ? updater(globalFilter) : updater
            ),
        onRowSelectionChange: setRowSelection,
        getCoreRowModel: getCoreRowModel(),
        getSortedRowModel: getSortedRowModel(),
        getFilteredRowModel: getFilteredRowModel(),
        getPaginationRowModel: getPaginationRowModel(),
        autoResetPageIndex: true,
    })

    // Selection may refer to rows that no longer exist (e.g. after deletion)
    const selectedIds = rows
        .map((row) => row.id)
        .filter((id) => rowSelection[id])

    const handleDeleteDone = (result: DeleteResult) => {
        setPendingDelete(null)
        // Keep failed (and untouched) rows selected so they can be retried
        setRowSelection((selection) =>
            Object.fromEntries(
                Object.entries(selection).filter(
                    ([id]) => !result.deleted.includes(id)
                )
            )
        )
        if (result.failed.length === 0) {
            showAlert({
                message:
                    result.deleted.length === 1
                        ? i18n.t('1 dashboard deleted')
                        : i18n.t('{{n}} dashboards deleted', {
                              n: result.deleted.length,
                          }),
            })
        } else {
            const errors = [...new Set(result.failed.map((f) => f.message))]
            showAlert({
                critical: true,
                message: i18n.t(
                    '{{deleted}} deleted and {{failed}} failed, still selected ({{errors}})',
                    {
                        deleted: result.deleted.length,
                        failed: result.failed.length,
                        errors: errors.join('; '),
                        interpolation: { escapeValue: false },
                    }
                ),
            })
        }
        queryClient.invalidateQueries({ queryKey: DASHBOARDS_QUERY_KEY })
        // The other check's cached result may list the deleted dashboards
        // too: rerun it when it is shown next (this one reruns right away)
        queryClient.invalidateQueries({
            queryKey: [INTEGRITY_CHECK_QUERY_KEY],
            refetchType: 'none',
        })
        onDeleted()
    }

    const filteredCount = table.getFilteredRowModel().rows.length
    const { pageIndex, pageSize } = table.getState().pagination
    const visibleRows = table.getRowModel().rows
    const namesById = new Map(rows.map((r) => [r.id, r.name]))

    return (
        <>
            <div className={styles.toolbar}>
                <div className={styles.search}>
                    <Input
                        dense
                        placeholder={i18n.t('Search by name')}
                        // Supported at runtime, missing from the type definitions
                        {...({
                            ariaLabel: i18n.t('Search dashboards by name'),
                        } as object)}
                        value={globalFilter}
                        onChange={({ value }) => changeSearch(value ?? '')}
                        dataTest="search"
                    />
                </div>
                {isRefreshing && (
                    <output className={styles.refreshing}>
                        <CircularLoader extrasmall />
                        {i18n.t('Updating results…')}
                    </output>
                )}
                <Button
                    destructive
                    disabled={selectedIds.length === 0 || isRefreshing}
                    onClick={() => setPendingDelete(selectedIds)}
                    dataTest="delete-selected"
                >
                    {selectedIds.length === 0
                        ? i18n.t('Delete selected')
                        : i18n.t('Delete selected ({{n}})', {
                              n: selectedIds.length,
                          })}
                </Button>
            </div>
            <DataTable dataTest="dashboard-table">
                <DataTableHead>
                    {table.getHeaderGroups().map((headerGroup) => (
                        <DataTableRow key={headerGroup.id}>
                            {headerGroup.headers.map((header) => (
                                <DataTableColumnHeader
                                    key={header.id}
                                    {...(header.column.getCanSort() &&
                                    header.column.id !== 'select'
                                        ? {
                                              sortDirection: getSortDirection(
                                                  header.column
                                              ),
                                              sortIconTitle: i18n.t('Sort'),
                                              onSortIconClick: () =>
                                                  header.column.toggleSorting(),
                                          }
                                        : {})}
                                >
                                    {flexRender(
                                        header.column.columnDef.header,
                                        header.getContext()
                                    )}
                                </DataTableColumnHeader>
                            ))}
                        </DataTableRow>
                    ))}
                </DataTableHead>
                <DataTableBody>
                    {visibleRows.length > 0 ? (
                        visibleRows.map((row) => (
                            <DataTableRow
                                key={row.id}
                                selected={row.getIsSelected()}
                                dataTest="dashboard-row"
                            >
                                {row.getVisibleCells().map((cell) => (
                                    <DataTableCell key={cell.id}>
                                        {flexRender(
                                            cell.column.columnDef.cell,
                                            cell.getContext()
                                        )}
                                    </DataTableCell>
                                ))}
                            </DataTableRow>
                        ))
                    ) : (
                        <DataTableRow>
                            <DataTableCell
                                colSpan={String(columns.length)}
                                align="center"
                                dataTest="empty-state"
                            >
                                {rows.length === 0
                                    ? i18n.t(
                                          'No dashboards found by this check'
                                      )
                                    : i18n.t('No dashboards match the search')}
                            </DataTableCell>
                        </DataTableRow>
                    )}
                </DataTableBody>
                {filteredCount > 0 && (
                    <DataTableFoot>
                        <DataTableRow>
                            <DataTableCell colSpan={String(columns.length)}>
                                <Pagination
                                    page={pageIndex + 1}
                                    pageSize={pageSize}
                                    pageCount={table.getPageCount()}
                                    total={filteredCount}
                                    onPageChange={(page: number) =>
                                        table.setPageIndex(page - 1)
                                    }
                                    onPageSizeChange={(size: number) =>
                                        table.setPageSize(size)
                                    }
                                />
                            </DataTableCell>
                        </DataTableRow>
                    </DataTableFoot>
                )}
            </DataTable>
            {pendingDelete && (
                <DeleteDashboardsModal
                    ids={pendingDelete}
                    names={pendingDelete.map((id) => namesById.get(id) ?? id)}
                    onCancel={() => setPendingDelete(null)}
                    onDone={handleDeleteDone}
                />
            )}
        </>
    )
}
