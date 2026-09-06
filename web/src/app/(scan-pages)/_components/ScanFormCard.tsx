'use client'

import ScanForm from '@/app/(scan-pages)/_components/ScanForm/ScanForm'
import { useScanForm } from '@/app/(scan-pages)/_hooks/useScanForm'

/** The client root of the form page: it owns what has been typed, and nothing else. */
const ScanFormCard = () => {
    const {
        domainsText,
        capHint,
        submitLabel,
        isRefused,
        isSubmitDisabled,
        handleDomainsChange,
        handleFileLoaded,
        handleClear,
        handleSubmit,
    } = useScanForm()

    return (
        <ScanForm
            domainsText={domainsText}
            capHint={capHint}
            submitLabel={submitLabel}
            isRefused={isRefused}
            isSubmitDisabled={isSubmitDisabled}
            onDomainsChange={handleDomainsChange}
            onFileLoaded={handleFileLoaded}
            onClear={handleClear}
            onSubmit={handleSubmit}
        />
    )
}

export default ScanFormCard
