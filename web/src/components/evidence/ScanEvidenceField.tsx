import CodeText from '@/components/ui/CodeText'

export type ScanEvidenceFieldProps = {
    label: string
    value: string | null
}

const ScanEvidenceField = ({ label, value }: ScanEvidenceFieldProps) => {
    if (value) {
        return (
            <div className="flex flex-col gap-1">
                <span className="text-xs uppercase tracking-wide text-ink-faint">{label}</span>
                <CodeText>{value}</CodeText>
            </div>
        )
    }

    return null
}

export default ScanEvidenceField
