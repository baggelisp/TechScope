import { COPY } from '@/constants/copy.constant'

export type DomainScanEmptyProps = {
    isVisible: boolean
}

const DomainScanEmpty = ({ isVisible }: DomainScanEmptyProps) => {
    if (isVisible) {
        return (
            <div className="rounded-xl border border-line bg-surface p-6 text-sm text-ink-muted">
                {COPY.domainEmpty}
            </div>
        )
    }

    return null
}

export default DomainScanEmpty
