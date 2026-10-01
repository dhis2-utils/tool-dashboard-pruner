import { CssReset, CssVariables } from '@dhis2/ui'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'
import { createHashRouter, RouterProvider } from 'react-router-dom'
import { PrunerPage } from '@/components/PrunerPage'
import { SyncUrlWithGlobalShell } from '@/utils/SyncUrlWithGlobalShell'
import './locales'

const queryClient = new QueryClient()

const router = createHashRouter([
    {
        element: <SyncUrlWithGlobalShell />,
        children: [{ path: '/', element: <PrunerPage /> }],
    },
])

const App = () => (
    <QueryClientProvider client={queryClient}>
        <CssReset />
        <CssVariables theme spacers colors elevations />
        <RouterProvider router={router} />
    </QueryClientProvider>
)

export default App
