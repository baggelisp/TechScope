import DomainScanDetailHeading from './DomainScanDetailHeading'
import DomainScanDetectionList from './DomainScanDetectionList'
import DomainScanEmpty from './DomainScanEmpty'
import DomainScanOverview from './DomainScanOverview'
import DomainScanProblemList from './DomainScanProblemList'
import DomainScanTechnologyList from './DomainScanTechnologyList'
import type { DomainResult } from '@/api/schemas'

export type DomainScanProps = {
    domain: DomainResult
}

/** The domain in summary, then every technology it runs explained one at a time. */
const DomainScan = ({ domain }: DomainScanProps) => {
    return (
        <div className="flex flex-col gap-6">
            <DomainScanOverview domain={domain} />
            <DomainScanProblemList problems={domain.problems} />
            <DomainScanTechnologyList detections={domain.detections} />
            <DomainScanEmpty isVisible={domain.detections.length === 0} />
            <DomainScanDetailHeading isVisible={domain.detections.length > 0} />
            <DomainScanDetectionList detections={domain.detections} />
        </div>
    )
}

export default DomainScan
