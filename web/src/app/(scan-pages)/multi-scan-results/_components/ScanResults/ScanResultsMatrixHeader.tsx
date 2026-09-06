import ScanResultsMatrixHeaderCell from './ScanResultsMatrixHeaderCell'
import { COPY } from '@/constants/copy.constant'

export type ScanResultsMatrixHeaderProps = {
    technologies: string[]
}

const ScanResultsMatrixHeader = ({ technologies }: ScanResultsMatrixHeaderProps) => {
    return (
        <thead>
            <tr className="border-b border-line bg-surface-raised">
                <th
                    scope="col"
                    className="sticky left-0 z-10 bg-surface-raised px-3 py-3 text-left text-xs font-semibold uppercase tracking-wide text-ink-faint sm:px-4"
                >
                    {COPY.resultsMatrixDomainHeader}
                </th>
                {technologies.map((technology) => (
                    <ScanResultsMatrixHeaderCell key={technology} technology={technology} />
                ))}
            </tr>
        </thead>
    )
}

export default ScanResultsMatrixHeader
