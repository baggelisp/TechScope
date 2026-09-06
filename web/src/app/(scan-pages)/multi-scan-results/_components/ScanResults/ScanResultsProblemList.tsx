import ScanResultsProblemListItem from './ScanResultsProblemListItem'
import type { DomainResult } from '@/api/schemas'
import Card from '@/components/ui/Card'
import { COPY } from '@/constants/copy.constant'

export type ScanResultsProblemListProps = {
    domains: DomainResult[]
}

const ScanResultsProblemList = ({ domains }: ScanResultsProblemListProps) => {
    if (domains.length > 0) {
        return (
            <Card tone="warning">
                <div className="flex flex-col gap-3">
                    <h3 className="text-sm font-semibold text-peach">
                        {COPY.resultsProblemsHeading}
                    </h3>
                    <ul className="flex flex-col gap-2">
                        {domains.map((domain) => (
                            <ScanResultsProblemListItem key={domain.domain} domain={domain} />
                        ))}
                    </ul>
                </div>
            </Card>
        )
    }

    return null
}

export default ScanResultsProblemList
