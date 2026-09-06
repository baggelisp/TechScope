import DomainScanTechnologyListItem from './DomainScanTechnologyListItem'
import type { Detection } from '@/api/schemas'
import Card from '@/components/ui/Card'
import { COPY } from '@/constants/copy.constant'

export type DomainScanTechnologyListProps = {
    detections: Detection[]
}

/** Everything found, at a glance, before the page explains each one in turn. */
const DomainScanTechnologyList = ({ detections }: DomainScanTechnologyListProps) => {
    if (detections.length > 0) {
        return (
            <Card tone="plain">
                <div className="flex flex-col gap-3">
                    <span className="text-xs font-medium uppercase tracking-widest text-ink-faint">
                        {COPY.domainTechnologiesHeading}
                    </span>
                    <ul className="flex flex-wrap gap-2">
                        {detections.map((detection) => (
                            <DomainScanTechnologyListItem
                                key={detection.name}
                                detection={detection}
                            />
                        ))}
                    </ul>
                </div>
            </Card>
        )
    }

    return null
}

export default DomainScanTechnologyList
