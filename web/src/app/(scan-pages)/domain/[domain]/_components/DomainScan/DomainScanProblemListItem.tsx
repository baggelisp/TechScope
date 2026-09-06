import type { Problem } from '@/api/schemas'
import { COPY } from '@/constants/copy.constant'

export type DomainScanProblemListItemProps = {
    problem: Problem
}

const DomainScanProblemListItem = ({ problem }: DomainScanProblemListItemProps) => {
    return (
        <li className="flex flex-col gap-0.5 text-sm">
            <span className="font-medium text-ink">
                {problem.collector}
                {COPY.resultsProblemSeparator}
                {problem.reason}
            </span>
            <span className="text-xs text-ink-muted">{problem.detail}</span>
        </li>
    )
}

export default DomainScanProblemListItem
