import ScanResults from './ScanResults/ScanResults'
import ScanResultsPageHeader from './ScanResultsPageHeader'
import { runScan } from '@/app/actions/scans/runScan'
import PageContainer from '@/components/layout/PageContainer'
import SiteHeader from '@/components/layout/SiteHeader'
import PageError from '@/components/shared/PageError'
import { COPY } from '@/constants/copy.constant'

export type ScanResultsViewProps = {
    domains: string[]
}

/** The scan runs here, on the server, while the browser shows the route's `loading.tsx`. */
const ScanResultsView = async ({ domains }: ScanResultsViewProps) => {
    const result = await runScan({ domains })

    if (result.success) {
        return (
            <div className="min-h-screen bg-canvas">
                <SiteHeader />
                <PageContainer>
                    <ScanResultsPageHeader report={result.data} />
                    <ScanResults report={result.data} />
                </PageContainer>
            </div>
        )
    }

    return (
        <div className="min-h-screen bg-canvas">
            <SiteHeader />
            <PageContainer>
                <ScanResultsPageHeader report={null} />
                <PageError
                    title={COPY.errorHeading}
                    message={result.error.message}
                    code={result.error.code}
                />
            </PageContainer>
        </div>
    )
}

export default ScanResultsView
