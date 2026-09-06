import { describe, expect, it } from 'vitest'

import RedirectUtility from '@/utils/RedirectUtility'

describe('RedirectUtility.decideRedirectOrNull', () => {
    it('answers null when nothing was observed', () => {
        expect(RedirectUtility.decideRedirectOrNull('a.com', null)).toBeNull()
    })

    it('answers null when the page came from the domain itself', () => {
        expect(RedirectUtility.decideRedirectOrNull('a.com', 'https://a.com/pricing')).toBeNull()
    })

    it('treats www as the same host', () => {
        expect(RedirectUtility.decideRedirectOrNull('a.com', 'https://www.a.com/')).toBeNull()
    })

    it('reports a redirect to another company', () => {
        expect(RedirectUtility.decideRedirectOrNull('drift.com', 'https://www.salesloft.com/x')).toBe(
            'https://www.salesloft.com/x',
        )
    })

    it('reports a look-alike host that merely contains the domain', () => {
        const observed = 'https://example.com.evil.tld/landing'

        expect(RedirectUtility.decideRedirectOrNull('example.com', observed)).toBe(observed)
    })

    it('reports a different host that merely contains the domain as a substring', () => {
        expect(RedirectUtility.decideRedirectOrNull('a.io', 'https://data.io/x')).toBe(
            'https://data.io/x',
        )
    })

    it('reports rather than hides a URL it cannot parse', () => {
        expect(RedirectUtility.decideRedirectOrNull('a.com', 'not a url')).toBe('not a url')
    })
})
