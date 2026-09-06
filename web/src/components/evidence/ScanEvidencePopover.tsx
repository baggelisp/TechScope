import ScanEvidenceList from './ScanEvidenceList'
import type { Detection } from '@/api/schemas'
import Button from '@/components/ui/Button'
import { COPY } from '@/constants/copy.constant'

export type ScanEvidencePopoverProps = {
    anchorId: string
    detection: Detection
    domainName: string
}

/**
 * What was actually observed, for one technology on one domain.
 *
 * A native popover: the browser opens it, closes it on Escape and on a click outside, and puts
 * it in the top layer. None of that needs JavaScript of ours.
 */
const ScanEvidencePopover = ({ anchorId, detection, domainName }: ScanEvidencePopoverProps) => {
    return (
        <div
            id={anchorId}
            popover="auto"
            aria-labelledby={`${anchorId}-title`}
            className="m-auto max-h-[85vh] w-[min(40rem,94vw)] overflow-y-auto rounded-xl border border-line bg-surface p-3 text-left text-ink sm:p-6"
        >
            <div className="flex flex-col gap-4">
                <div className="flex items-start justify-between gap-4">
                    <div className="flex flex-col gap-1">
                        <h3
                            id={`${anchorId}-title`}
                            className="text-base font-semibold text-ink"
                        >
                            {detection.name} on {domainName}
                        </h3>
                        <p className="text-xs text-ink-muted">
                            {detection.confidence}% {COPY.evidenceConfidence}
                        </p>
                    </div>
                    <Button variant="ghost" popoverTarget={anchorId} popoverTargetAction="hide">
                        {COPY.evidenceClose}
                    </Button>
                </div>
                <ScanEvidenceList evidence={detection.evidence} />
            </div>
        </div>
    )
}

export default ScanEvidencePopover
