import type { Detection } from '@/api/schemas'
import { COPY } from '@/constants/copy.constant'

export type DomainScanTechnologyListItemProps = {
    detection: Detection
}

/** A jump to the card that explains this one, so the summary is a table of contents. */
const DomainScanTechnologyListItem = ({ detection }: DomainScanTechnologyListItemProps) => {
    return (
        <li>
            <a
                href={`#${buildDetectionAnchorId(detection.name)}`}
                className="flex items-center gap-2 rounded-md bg-accent/10 px-3 py-1.5 text-sm font-medium text-accent ring-1 ring-accent/25 transition-colors hover:bg-accent/20"
            >
                <span>{detection.name}</span>
                <span className="text-xs text-accent/70">
                    {detection.evidence.length} {COPY.domainSignalsShort}
                </span>
            </a>
        </li>
    )
}

export default DomainScanTechnologyListItem

export function buildDetectionAnchorId(name: string): string {
    return `technology-${name.replace(/[^a-zA-Z0-9]+/g, '-').toLowerCase()}`
}
