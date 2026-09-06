import type { DomainResult } from '@/api/schemas'
import { COPY } from '@/constants/copy.constant'

export type ScanResultsProblemListItemProps = {
    domain: DomainResult
}

const ScanResultsProblemListItem = ({ domain }: ScanResultsProblemListItemProps) => {
    const reasons = domain.problems.map((problem) => problem.reason).join(COPY.evidenceLabelJoiner)
    const detail = decideDetail(domain)

    return (
        <li className="flex flex-col gap-0.5 text-sm">
            <span className="font-medium text-ink">
                {domain.domain}
                {COPY.resultsProblemSeparator}
                {reasons}
            </span>
            <span className="text-xs text-ink-muted">{detail}</span>
        </li>
    )
}

export default ScanResultsProblemListItem

function decideDetail(domain: DomainResult): string {
    const details = domain.problems.map((problem) => problem.detail)

    if (details.length > 0) return details.join(COPY.resultsProblemDetailSeparator)

    return COPY.resultsNoDetections
}
