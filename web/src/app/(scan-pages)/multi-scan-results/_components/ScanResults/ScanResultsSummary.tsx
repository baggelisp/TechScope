import ScanResultsSummaryStat from './ScanResultsSummaryStat'
import type { ScanSummary } from '@/api/schemas'
import { COPY } from '@/constants/copy.constant'

export type ScanResultsSummaryProps = {
    summary: ScanSummary
}

const ScanResultsSummary = ({ summary }: ScanResultsSummaryProps) => {
    return (
        <div className="grid grid-cols-2 gap-2 sm:gap-3 lg:grid-cols-4">
            <ScanResultsSummaryStat label={COPY.summaryDomains} value={summary.domains} />
            <ScanResultsSummaryStat label={COPY.summaryDetections} value={summary.detections} />
            <ScanResultsSummaryStat
                label={COPY.summaryProblems}
                value={summary.domains_with_problems}
            />
            <ScanResultsSummaryStat label={COPY.summarySeconds} value={summary.duration_seconds} />
        </div>
    )
}

export default ScanResultsSummary
