import { buildDetectionAnchorId } from './DomainScanTechnologyListItem'
import type { Detection } from '@/api/schemas'
import ScanEvidenceList from '@/components/evidence/ScanEvidenceList'
import Card from '@/components/ui/Card'
import Tag from '@/components/ui/Tag'
import { COPY } from '@/constants/copy.constant'

export type DomainScanDetectionListItemProps = {
    detection: Detection
}

/** One technology, with every signal that proved it open on the page. */
const DomainScanDetectionListItem = ({ detection }: DomainScanDetectionListItemProps) => {
    return (
        <li id={buildDetectionAnchorId(detection.name)} className="scroll-mt-6">
            <Card tone="plain">
                <div className="flex flex-col gap-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                        <h3 className="text-base font-semibold tracking-tight text-ink sm:text-lg">
                            {detection.name}
                        </h3>
                        <Tag tone="accent">
                            {detection.confidence}% {COPY.evidenceConfidence}
                        </Tag>
                    </div>
                    <div className="flex flex-col gap-2">
                        <span className="text-xs font-medium uppercase tracking-widest text-ink-faint">
                            {COPY.domainEvidenceHeading}
                        </span>
                        <ScanEvidenceList evidence={detection.evidence} />
                    </div>
                </div>
            </Card>
        </li>
    )
}

export default DomainScanDetectionListItem
