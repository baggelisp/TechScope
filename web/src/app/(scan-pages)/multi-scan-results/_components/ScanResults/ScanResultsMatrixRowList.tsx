import ScanResultsMatrixRow from './ScanResultsMatrixRow'
import type { DomainResult } from '@/api/schemas'

export type ScanResultsMatrixRowListProps = {
    domains: DomainResult[]
    technologies: string[]
}

const ScanResultsMatrixRowList = ({ domains, technologies }: ScanResultsMatrixRowListProps) => {
    return (
        <tbody>
            {domains.map((domain, rowIndex) => (
                <ScanResultsMatrixRow
                    key={domain.domain}
                    domain={domain}
                    technologies={technologies}
                    rowIndex={rowIndex}
                />
            ))}
        </tbody>
    )
}

export default ScanResultsMatrixRowList
