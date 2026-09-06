import { COPY } from '@/constants/copy.constant'

export type ScanResultsEmptyProps = {
    isVisible: boolean
}

const ScanResultsEmpty = ({ isVisible }: ScanResultsEmptyProps) => {
    if (isVisible) {
        return (
            <div className="rounded-xl border border-line bg-surface p-6 text-sm text-ink-muted">
                {COPY.resultsEmpty}
            </div>
        )
    }

    return null
}

export default ScanResultsEmpty
