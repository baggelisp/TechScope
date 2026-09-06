import ScanResultsMatrixCell from './ScanResultsMatrixCell'
import ScanResultsMatrixRowDomain from './ScanResultsMatrixRowDomain'
import type { DomainResult } from '@/api/schemas'

export type ScanResultsMatrixRowProps = {
    domain: DomainResult
    technologies: string[]
    rowIndex: number
}

const ScanResultsMatrixRow = ({ domain, technologies, rowIndex }: ScanResultsMatrixRowProps) => {
    return (
        <tr className="border-b border-line/60 last:border-b-0 hover:bg-white/[0.02]">
            <ScanResultsMatrixRowDomain domain={domain} />
            {technologies.map((technology, columnIndex) => (
                <ScanResultsMatrixCell
                    key={technology}
                    domain={domain}
                    technology={technology}
                    rowIndex={rowIndex}
                    columnIndex={columnIndex}
                />
            ))}
        </tr>
    )
}

export default ScanResultsMatrixRow
