'use client'

/**
 * The form's own state, and where submitting it goes.
 *
 * The scan itself is not here: submitting navigates to the page that will run it, and that page
 * runs it on the server. What this does keep is the two bounds the API also enforces, checked
 * before the navigation rather than after it, so a mis-dropped file is a sentence on the form
 * instead of a bare error from a server refusing an enormous URL.
 */

import { useRouter } from 'next/navigation'
import { useState, useTransition } from 'react'

import { COPY } from '@/constants/copy.constant'
import { MAXIMUM_DOMAIN_LENGTH, MAXIMUM_SUBMITTED_DOMAINS } from '@/constants/scan.constant'
import DomainListUtility from '@/utils/DomainListUtility'
import ScanDestinationUtility from '@/utils/ScanDestinationUtility'

export const useScanForm = () => {
    const router = useRouter()
    const [domainsText, setDomainsText] = useState('')
    const [isNavigating, startNavigation] = useTransition()

    const domains = DomainListUtility.parse(domainsText)
    const isOverTheCap = domains.length > MAXIMUM_SUBMITTED_DOMAINS
    const hasOversizedEntry = DomainListUtility.hasEntryLongerThan(domainsText, MAXIMUM_DOMAIN_LENGTH)
    const isRefused = isOverTheCap || hasOversizedEntry
    const isSubmitDisabled = domains.length === 0 || isRefused || isNavigating
    const capHint = decideCapHint(domains.length, isOverTheCap, hasOversizedEntry)
    const submitLabel = decideSubmitLabel(isNavigating)

    const handleDomainsChange = (value: string) => {
        setDomainsText(value)
    }

    const handleFileLoaded = (contents: string) => {
        setDomainsText(contents)
    }

    const handleClear = () => {
        setDomainsText('')
    }

    const handleSubmit = () => {
        if (isSubmitDisabled) return

        const destination = ScanDestinationUtility.decideDestination(domains)

        startNavigation(() => {
            router.push(destination)
        })
    }

    return {
        domainsText,
        capHint,
        submitLabel,
        isRefused,
        isSubmitDisabled,
        handleDomainsChange,
        handleFileLoaded,
        handleClear,
        handleSubmit,
    }
}

function decideCapHint(count: number, isOverTheCap: boolean, hasOversizedEntry: boolean): string {
    if (hasOversizedEntry) return COPY.formEntryTooLong

    if (isOverTheCap) return `${count}${COPY.formOverTheCap}`

    if (count === 0) return COPY.formLimitHint

    return `${count}${COPY.formReadyToScan}`
}

function decideSubmitLabel(isNavigating: boolean): string {
    if (isNavigating) return COPY.formSubmitPending

    return COPY.formSubmit
}
