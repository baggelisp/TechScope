import ScanResultsMatrixCellMark from './ScanResultsMatrixCellMark'
import type { DomainResult } from '@/api/schemas'
import ScanReportUtility from '@/utils/ScanReportUtility'

export type ScanResultsMatrixCellProps = {
    domain: DomainResult
    technology: string
    rowIndex: number
    columnIndex: number
}

const ScanResultsMatrixCell = ({
    domain,
    technology,
    rowIndex,
    columnIndex,
}: ScanResultsMatrixCellProps) => {
    const detection = ScanReportUtility.decideDetectionOrNull(domain, technology)

    return (
        <td className="px-3 py-3 text-center align-middle">
            <ScanResultsMatrixCellMark
                detection={detection}
                technology={technology}
                domainName={domain.domain}
                rowIndex={rowIndex}
                columnIndex={columnIndex}
            />
        </td>
    )
}

export default ScanResultsMatrixCell
