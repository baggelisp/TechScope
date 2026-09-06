export type DomainScanOverviewFactProps = {
    label: string
    value: string
}

const DomainScanOverviewFact = ({ label, value }: DomainScanOverviewFactProps) => {
    return (
        <div className="flex flex-col gap-1">
            <span className="text-xs font-medium uppercase tracking-widest text-ink-faint">
                {label}
            </span>
            <span className="break-all text-sm font-medium text-ink">{value}</span>
        </div>
    )
}

export default DomainScanOverviewFact
