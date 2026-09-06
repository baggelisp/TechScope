import ScanResultsMatrixCellBlank from './ScanResultsMatrixCellBlank'
import type { Detection } from '@/api/schemas'
import ScanEvidencePopover from '@/components/evidence/ScanEvidencePopover'
import CheckIcon from '@/components/ui/CheckIcon'
import { COPY } from '@/constants/copy.constant'
import { FULL_CONFIDENCE } from '@/constants/scan.constant'
import EvidenceAnchorUtility from '@/utils/EvidenceAnchorUtility'

export type ScanResultsMatrixCellMarkProps = {
    detection: Detection | null
    technology: string
    domainName: string
    rowIndex: number
    columnIndex: number
}

/**
 * A detection is a tick that opens its evidence; an absence is a dash.
 *
 * The tick is dimmed below full confidence, so the column still says how sure the scanner is
 * without a number in every cell. The exact figure is in the panel the tick opens, and in the
 * label a screen reader reads.
 *
 * The button and the popover are tied by an id, which the browser acts on itself. That is what
 * keeps this a server component: there is no handler and no state to hold the pair together.
 */
const ScanResultsMatrixCellMark = ({
    detection,
    technology,
    domainName,
    rowIndex,
    columnIndex,
}: ScanResultsMatrixCellMarkProps) => {
    if (detection) {
        const anchorId = EvidenceAnchorUtility.buildId(rowIndex, columnIndex)
        const label = `${technology}${COPY.evidenceOnJoiner}${domainName}${COPY.evidenceLabelJoiner}${detection.confidence}% ${COPY.evidenceConfidence}`

        return (
            <div className="inline-flex">
                <button
                    type="button"
                    popoverTarget={anchorId}
                    title={label}
                    aria-label={label}
                    className="flex size-7 items-center justify-center rounded-md bg-accent/10 ring-1 ring-accent/20 transition-colors hover:bg-accent/25"
                >
                    <CheckIcon isDimmed={detection.confidence < FULL_CONFIDENCE} />
                </button>
                <ScanEvidencePopover
                    anchorId={anchorId}
                    detection={detection}
                    domainName={domainName}
                />
            </div>
        )
    }

    return <ScanResultsMatrixCellBlank />
}

export default ScanResultsMatrixCellMark
