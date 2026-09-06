'use client'

import { useRef, useState, type ChangeEvent, type DragEvent } from 'react'

import ScanFormFileButton from './ScanFormFileButton'
import { COPY } from '@/constants/copy.constant'
import { DOMAINS_TEXTAREA_ROWS } from '@/constants/scan.constant'

export type ScanFormDomainsFieldProps = {
    value: string
    onChange: (value: string) => void
    onFileLoaded: (contents: string) => void
}

const ScanFormDomainsField = ({ value, onChange, onFileLoaded }: ScanFormDomainsFieldProps) => {
    const [isDropTarget, setIsDropTarget] = useState(false)
    const textareaRef = useRef<HTMLTextAreaElement>(null)

    const handleChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
        onChange(event.target.value)
    }

    const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
        event.preventDefault()
        setIsDropTarget(true)
    }

    const handleDragLeave = () => {
        setIsDropTarget(false)
    }

    const handleDrop = async (event: DragEvent<HTMLDivElement>) => {
        event.preventDefault()
        setIsDropTarget(false)

        const file = event.dataTransfer.files.item(0)

        if (file) {
            onFileLoaded(await file.text())
            textareaRef.current?.focus()
        }
    }

    const borderClassName = decideBorderClassName(isDropTarget)

    return (
        <div
            className={`flex flex-col gap-3 rounded-lg border-2 border-dashed p-2 transition-colors sm:p-3 ${borderClassName}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
        >
            <textarea
                ref={textareaRef}
                value={value}
                onChange={handleChange}
                rows={DOMAINS_TEXTAREA_ROWS}
                spellCheck={false}
                placeholder={COPY.formPlaceholder}
                aria-label={COPY.formHeading}
                className="w-full resize-y rounded-lg border border-line bg-canvas p-3 font-mono text-sm text-ink outline-none placeholder:text-ink-faint focus:border-accent/60"
            />
            <div className="flex flex-wrap items-center gap-3">
                <ScanFormFileButton onFileLoaded={onFileLoaded} />
                <span className="text-xs text-ink-faint">{COPY.formFileDropHint}</span>
            </div>
        </div>
    )
}

export default ScanFormDomainsField

function decideBorderClassName(isDropTarget: boolean): string {
    if (isDropTarget) return 'border-accent bg-accent/5'

    return 'border-transparent'
}
