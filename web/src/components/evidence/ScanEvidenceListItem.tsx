import ScanEvidenceChannelTag from './ScanEvidenceChannelTag'
import ScanEvidenceField from './ScanEvidenceField'
import type { Evidence } from '@/api/schemas'
import { COPY } from '@/constants/copy.constant'

export type ScanEvidenceListItemProps = {
    evidence: Evidence
}

const ScanEvidenceListItem = ({ evidence }: ScanEvidenceListItemProps) => {
    return (
        <li className="rounded-lg border border-line bg-surface-raised p-3 sm:p-4">
            <div className="flex flex-col gap-3">
                <ScanEvidenceChannelTag channel={evidence.channel} />
                <ScanEvidenceField label={COPY.evidenceKey} value={evidence.key} />
                <ScanEvidenceField label={COPY.evidencePattern} value={evidence.pattern} />
                <ScanEvidenceField label={COPY.evidenceMatched} value={evidence.matched} />
            </div>
        </li>
    )
}

export default ScanEvidenceListItem
