import DomainScanDetectionListItem from './DomainScanDetectionListItem'
import type { Detection } from '@/api/schemas'

export type DomainScanDetectionListProps = {
    detections: Detection[]
}

const DomainScanDetectionList = ({ detections }: DomainScanDetectionListProps) => {
    if (detections.length > 0) {
        return (
            <ul className="flex flex-col gap-4">
                {detections.map((detection) => (
                    <DomainScanDetectionListItem key={detection.name} detection={detection} />
                ))}
            </ul>
        )
    }

    return null
}

export default DomainScanDetectionList
