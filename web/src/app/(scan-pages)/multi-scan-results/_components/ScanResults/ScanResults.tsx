import ScanResultsEmpty from './ScanResultsEmpty'
import ScanResultsMatrix from './ScanResultsMatrix'
import ScanResultsProblemList from './ScanResultsProblemList'
import ScanResultsSummary from './ScanResultsSummary'
import type { ScanReport } from '@/api/schemas'
import ScanReportUtility from '@/utils/ScanReportUtility'

export type ScanResultsProps = {
    report: ScanReport
}

/**
 * A server component, and so is everything under it but the download button.
 *
 * The evidence popovers are opened by the browser rather than by React, so nothing here needs
 * state and nothing here ships to the browser.
 */
const ScanResults = ({ report }: ScanResultsProps) => {
    const technologies = ScanReportUtility.listTechnologyNames(report)
    const troubled = ScanReportUtility.listTroubledDomains(report)

    return (
        <section className="flex flex-col gap-6">
            <ScanResultsSummary summary={report.summary} />
            <ScanResultsEmpty isVisible={technologies.length === 0} />
            <ScanResultsMatrix domains={report.domains} technologies={technologies} />
            <ScanResultsProblemList domains={troubled} />
        </section>
    )
}

export default ScanResults
