'use client'

import ScanFormDomainsField from './ScanFormDomainsField'
import ScanFormFooter from './ScanFormFooter'
import Card from '@/components/ui/Card'
import { COPY } from '@/constants/copy.constant'

export type ScanFormProps = {
    domainsText: string
    capHint: string
    submitLabel: string
    isRefused: boolean
    isSubmitDisabled: boolean
    onDomainsChange: (value: string) => void
    onFileLoaded: (contents: string) => void
    onClear: () => void
    onSubmit: () => void
}

const ScanForm = ({
    domainsText,
    capHint,
    submitLabel,
    isRefused,
    isSubmitDisabled,
    onDomainsChange,
    onFileLoaded,
    onClear,
    onSubmit,
}: ScanFormProps) => {
    return (
        <Card tone="plain">
            <div className="flex flex-col gap-4">
                <div className="flex flex-col gap-1">
                    <h2 className="text-sm font-semibold text-ink">{COPY.formHeading}</h2>
                    <p className="text-sm text-ink-muted">{COPY.formHint}</p>
                </div>
                <ScanFormDomainsField
                    value={domainsText}
                    onChange={onDomainsChange}
                    onFileLoaded={onFileLoaded}
                />
                <ScanFormFooter
                    capHint={capHint}
                    submitLabel={submitLabel}
                    isRefused={isRefused}
                    isSubmitDisabled={isSubmitDisabled}
                    onClear={onClear}
                    onSubmit={onSubmit}
                />
            </div>
        </Card>
    )
}

export default ScanForm
