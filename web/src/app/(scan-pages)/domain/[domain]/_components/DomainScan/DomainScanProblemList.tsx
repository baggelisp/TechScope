import DomainScanProblemListItem from './DomainScanProblemListItem'
import type { Problem } from '@/api/schemas'
import Card from '@/components/ui/Card'
import { COPY } from '@/constants/copy.constant'

export type DomainScanProblemListProps = {
    problems: Problem[]
}

const DomainScanProblemList = ({ problems }: DomainScanProblemListProps) => {
    if (problems.length > 0) {
        return (
            <Card tone="warning">
                <div className="flex flex-col gap-3">
                    <h2 className="text-sm font-semibold text-peach">
                        {COPY.domainProblemsHeading}
                    </h2>
                    <ul className="flex flex-col gap-2">
                        {problems.map((problem) => (
                            <DomainScanProblemListItem
                                key={`${problem.collector}-${problem.reason}`}
                                problem={problem}
                            />
                        ))}
                    </ul>
                </div>
            </Card>
        )
    }

    return null
}

export default DomainScanProblemList
