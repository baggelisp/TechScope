import DomainScanOverviewFact from './DomainScanOverviewFact'
import type { DomainResult } from '@/api/schemas'
import Card from '@/components/ui/Card'
import { COPY } from '@/constants/copy.constant'
import RedirectUtility from '@/utils/RedirectUtility'

export type DomainScanOverviewProps = {
    domain: DomainResult
}

const DomainScanOverview = ({ domain }: DomainScanOverviewProps) => {
    const redirect = RedirectUtility.decideRedirectOrNull(domain.domain, domain.observed_url)
    const readFrom = decideReadFrom(redirect)
    const signalCount = domain.detections.reduce(
        (total, detection) => total + detection.evidence.length,
        0,
    )

    return (
        <Card tone="plain">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 sm:gap-5">
                <DomainScanOverviewFact label={COPY.domainDetections} value={String(domain.detections.length)} />
                <DomainScanOverviewFact label={COPY.domainSignals} value={String(signalCount)} />
                <DomainScanOverviewFact label={COPY.domainDuration} value={decideDuration(domain)} />
            </div>
            <div className="mt-4 border-t border-line pt-4 sm:mt-5 sm:pt-5">
                <DomainScanOverviewFact label={COPY.domainReadFrom} value={readFrom} />
            </div>
        </Card>
    )
}

export default DomainScanOverview

function decideReadFrom(redirect: string | null): string {
    if (redirect) return redirect

    return COPY.domainSameHost
}

function decideDuration(domain: DomainResult): string {
    const seconds = domain.duration_seconds

    if (seconds === null) return '-'

    return String(seconds)
}
