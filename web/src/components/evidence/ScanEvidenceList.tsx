import ScanEvidenceListItem from './ScanEvidenceListItem'
import type { Evidence } from '@/api/schemas'

export type ScanEvidenceListProps = {
    evidence: Evidence[]
}

const ScanEvidenceList = ({ evidence }: ScanEvidenceListProps) => {
    return (
        <ul className="flex flex-col gap-3">
            {evidence.map((entry, index) => (
                <ScanEvidenceListItem key={buildEvidenceKey(entry, index)} evidence={entry} />
            ))}
        </ul>
    )
}

export default ScanEvidenceList

function buildEvidenceKey(evidence: Evidence, index: number): string {
    return `${evidence.channel}-${evidence.pattern}-${index}`
}
