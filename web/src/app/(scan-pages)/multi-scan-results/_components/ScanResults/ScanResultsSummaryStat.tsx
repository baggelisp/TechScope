export type ScanResultsSummaryStatProps = {
    label: string
    value: number
}

const ScanResultsSummaryStat = ({ label, value }: ScanResultsSummaryStatProps) => {
    return (
        <div className="flex flex-col gap-1 rounded-xl border border-line bg-surface px-4 py-3 sm:px-5 sm:py-4">
            <span className="text-xs font-medium uppercase tracking-widest text-ink-faint">
                {label}
            </span>
            <span className="text-2xl font-semibold tabular-nums tracking-tight text-ink sm:text-3xl">
                {value}
            </span>
        </div>
    )
}

export default ScanResultsSummaryStat
