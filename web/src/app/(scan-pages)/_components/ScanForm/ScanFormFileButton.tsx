'use client'

import { useRef, type ChangeEvent } from 'react'

import Button from '@/components/ui/Button'
import { COPY } from '@/constants/copy.constant'
import { DOMAINS_FILE_ACCEPT } from '@/constants/scan.constant'

export type ScanFormFileButtonProps = {
    onFileLoaded: (contents: string) => void
}

const ScanFormFileButton = ({ onFileLoaded }: ScanFormFileButtonProps) => {
    const inputRef = useRef<HTMLInputElement>(null)

    const handleClick = () => {
        inputRef.current?.click()
    }

    const handleChange = async (event: ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.item(0)

        if (file) {
            onFileLoaded(await file.text())
            event.target.value = ''
        }
    }

    return (
        <div className="inline-flex">
            <input
                ref={inputRef}
                type="file"
                accept={DOMAINS_FILE_ACCEPT}
                onChange={handleChange}
                className="hidden"
            />
            <Button variant="secondary" onClick={handleClick}>
                {COPY.formFileButton}
            </Button>
        </div>
    )
}

export default ScanFormFileButton
