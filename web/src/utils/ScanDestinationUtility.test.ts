import { describe, expect, it } from 'vitest'

import ScanDestinationUtility from '@/utils/ScanDestinationUtility'

describe('ScanDestinationUtility.decideDestination', () => {
    it('sends one domain to its own page', () => {
        expect(ScanDestinationUtility.decideDestination(['stripe.com'])).toBe('/domain/stripe.com')
    })

    it('escapes what it puts in the path', () => {
        expect(ScanDestinationUtility.decideDestination(['a b.com'])).toBe('/domain/a%20b.com')
    })

    it('sends two domains to the matrix', () => {
        expect(ScanDestinationUtility.decideDestination(['a.com', 'b.com'])).toBe(
            '/multi-scan-results?domains=a.com%0Ab.com',
        )
    })

    it('sends an empty list to the matrix, which redirects it back to the form', () => {
        expect(ScanDestinationUtility.decideDestination([])).toBe('/multi-scan-results?domains=')
    })
})

describe('ScanDestinationUtility.decideSingleDomainOrNull', () => {
    it('answers the domain when there is exactly one', () => {
        expect(ScanDestinationUtility.decideSingleDomainOrNull(['a.com'])).toBe('a.com')
    })

    it('answers null for none', () => {
        expect(ScanDestinationUtility.decideSingleDomainOrNull([])).toBeNull()
    })

    it('answers null for more than one', () => {
        expect(ScanDestinationUtility.decideSingleDomainOrNull(['a.com', 'b.com'])).toBeNull()
    })
})
