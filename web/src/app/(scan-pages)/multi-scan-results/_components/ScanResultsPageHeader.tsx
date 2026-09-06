import ScanResultsDownloadButton from './ScanResults/ScanResultsDownloadButton'
import type { ScanReport } from '@/api/schemas'
import BackLink from '@/components/shared/BackLink'
import ButtonRow from '@/components/ui/ButtonRow'
import { COPY } from '@/constants/copy.constant'
import { ROUTE } from '@/constants/route.constant'

export type ScanResultsPageHeaderProps = {
    report: ScanReport | null
}

/** The same chrome whether the scan produced results or an error; only the action differs. */
const ScanResultsPageHeader = ({ report }: ScanResultsPageHeaderProps) => {
    return (
        <div className="flex flex-col gap-4">
            <BackLink href={ROUTE.scanForm} label={COPY.backToForm} />
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                <div className="flex flex-col gap-1">
                    <h1 className="text-xl font-semibold tracking-tight text-ink sm:text-2xl">
                        {COPY.resultsHeading}
                    </h1>
                    <p className="text-sm text-ink-muted">{COPY.appTagline}</p>
                </div>
                <ButtonRow>
                    <ScanResultsDownloadButton report={report} />
                </ButtonRow>
            </div>
        </div>
    )
}

export default ScanResultsPageHeader
