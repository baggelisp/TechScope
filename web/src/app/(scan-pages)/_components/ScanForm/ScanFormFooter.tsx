'use client'

import Button from '@/components/ui/Button'
import ButtonRow from '@/components/ui/ButtonRow'
import { COPY } from '@/constants/copy.constant'

export type ScanFormFooterProps = {
    capHint: string
    submitLabel: string
    isRefused: boolean
    isSubmitDisabled: boolean
    onClear: () => void
    onSubmit: () => void
}

const ScanFormFooter = ({
    capHint,
    submitLabel,
    isRefused,
    isSubmitDisabled,
    onClear,
    onSubmit,
}: ScanFormFooterProps) => {
    const hintClassName = decideHintClassName(isRefused)

    return (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <span className={`text-xs ${hintClassName}`}>{capHint}</span>
            <ButtonRow>
                <Button variant="ghost" onClick={onClear}>
                    {COPY.formClear}
                </Button>
                <Button variant="primary" onClick={onSubmit} isDisabled={isSubmitDisabled}>
                    {submitLabel}
                </Button>
            </ButtonRow>
        </div>
    )
}

export default ScanFormFooter

function decideHintClassName(isRefused: boolean): string {
    if (isRefused) return 'font-medium text-peach'

    return 'text-ink-faint'
}
