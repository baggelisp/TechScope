import DomainScan from './DomainScan/DomainScan'
import DomainScanPageHeader from './DomainScanPageHeader'
import { runScan } from '@/app/actions/scans/runScan'
import type { ScanReport } from '@/api/schemas'
import PageContainer from '@/components/layout/PageContainer'
import SiteHeader from '@/components/layout/SiteHeader'
import PageError from '@/components/shared/PageError'
import { COPY } from '@/constants/copy.constant'
import type { ActionResponse } from '@/lib/utils/errors'
import type { DomainResult } from '@/api/schemas'

export type DomainScanViewProps = {
    domain: string
}

/**
 * One domain, in full.
 *
 * The matrix answers "which technologies", and for twenty domains at once that is the right
 * shape. This answers "why", for one: every detection with all of its evidence open on the page
 * rather than behind a popover, the URL the page was actually read from, and what went wrong.
 * It scans only the domain it is about, so it is cheap enough to be a link from any row.
 */
const DomainScanView = async ({ domain }: DomainScanViewProps) => {
    const result = await runScan({ domains: [domain] })
    const scanned = decideScannedOrNull(result)

    if (scanned) {
        return (
            <div className="min-h-screen bg-canvas">
                <SiteHeader />
                <PageContainer>
                    <DomainScanPageHeader domain={domain} />
                    <DomainScan domain={scanned} />
                </PageContainer>
            </div>
        )
    }

    return (
        <div className="min-h-screen bg-canvas">
            <SiteHeader />
            <PageContainer>
                <DomainScanPageHeader domain={domain} />
                <PageError
                    title={COPY.errorHeading}
                    message={decideMessage(result)}
                    code={decideCode(result)}
                />
            </PageContainer>
        </div>
    )
}

export default DomainScanView

function decideScannedOrNull(result: ActionResponse<ScanReport>): DomainResult | null {
    if (result.success) {
        const scanned = result.data.domains[0]

        if (scanned) return scanned
    }

    return null
}

function decideMessage(result: ActionResponse<ScanReport>): string {
    if (result.success) return COPY.domainEmpty

    return result.error.message
}

function decideCode(result: ActionResponse<ScanReport>): string {
    if (result.success) return COPY.errorNoDomainCode

    return result.error.code
}
