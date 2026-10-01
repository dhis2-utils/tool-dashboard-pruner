import i18n from '@dhis2/d2-i18n'
import {
    Button,
    ButtonStrip,
    Modal,
    ModalActions,
    ModalContent,
    ModalTitle,
} from '@dhis2/ui'
import React, { useState } from 'react'
import { DeleteResult, useDeleteDashboards } from '@/hooks/useDeleteDashboards'

const MAX_LISTED_NAMES = 10

type DeleteDashboardsModalProps = {
    ids: string[]
    names: string[]
    onCancel: () => void
    onDone: (result: DeleteResult) => void
}

export const DeleteDashboardsModal = ({
    ids,
    names,
    onCancel,
    onDone,
}: DeleteDashboardsModalProps) => {
    const [done, setDone] = useState(0)
    const { deleteDashboards, isDeleting } = useDeleteDashboards({
        onProgress: setDone,
        onSettled: onDone,
    })
    const count = ids.length

    return (
        <Modal
            small
            onClose={isDeleting ? undefined : onCancel}
            dataTest="delete-modal"
        >
            <ModalTitle>
                {count === 1
                    ? i18n.t('Delete 1 dashboard?')
                    : i18n.t('Delete {{n}} dashboards?', { n: count })}
            </ModalTitle>
            <ModalContent>
                <p>{i18n.t('This cannot be undone.')}</p>
                <ul>
                    {names.slice(0, MAX_LISTED_NAMES).map((name, i) => (
                        <li key={ids[i]}>{name}</li>
                    ))}
                    {count > MAX_LISTED_NAMES && (
                        <li>
                            {i18n.t('…and {{n}} more', {
                                n: count - MAX_LISTED_NAMES,
                            })}
                        </li>
                    )}
                </ul>
                {isDeleting && (
                    <p>
                        {i18n.t('Deleted {{done}} of {{total}}…', {
                            done,
                            total: count,
                        })}
                    </p>
                )}
            </ModalContent>
            <ModalActions>
                <ButtonStrip end>
                    <Button secondary onClick={onCancel} disabled={isDeleting}>
                        {i18n.t('Cancel')}
                    </Button>
                    <Button
                        destructive
                        loading={isDeleting}
                        disabled={isDeleting}
                        onClick={() => deleteDashboards(ids)}
                        dataTest="confirm-delete"
                    >
                        {i18n.t('Delete')}
                    </Button>
                </ButtonStrip>
            </ModalActions>
        </Modal>
    )
}
