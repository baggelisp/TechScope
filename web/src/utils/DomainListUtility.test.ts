import { describe, expect, it } from 'vitest'

import DomainListUtility from '@/utils/DomainListUtility'

describe('DomainListUtility.parse', () => {
    it('returns nothing for empty text', () => {
        expect(DomainListUtility.parse('')).toEqual([])
    })

    it('returns nothing for whitespace alone', () => {
        expect(DomainListUtility.parse('   \n\t\n  ')).toEqual([])
    })

    it('keeps one entry per line, trimmed', () => {
        expect(DomainListUtility.parse('  stripe.com \n shopify.com')).toEqual([
            'stripe.com',
            'shopify.com',
        ])
    })

    it('drops comments', () => {
        expect(DomainListUtility.parse('# a note\nstripe.com')).toEqual(['stripe.com'])
    })

    it('drops duplicates while keeping the first position', () => {
        expect(DomainListUtility.parse('a.com\nb.com\na.com')).toEqual(['a.com', 'b.com'])
    })

    it('reads carriage returns as line endings', () => {
        expect(DomainListUtility.parse('a.com\r\nb.com')).toEqual(['a.com', 'b.com'])
    })
})

describe('DomainListUtility.count', () => {
    it('counts nothing in empty text', () => {
        expect(DomainListUtility.count('')).toBe(0)
    })

    it('counts what parse would return', () => {
        expect(DomainListUtility.count('a.com\n\n# note\na.com\nb.com')).toBe(2)
    })
})

describe('DomainListUtility.hasEntryLongerThan', () => {
    it('answers false for empty text', () => {
        expect(DomainListUtility.hasEntryLongerThan('', 10)).toBe(false)
    })

    it('answers false when every entry is within the bound', () => {
        expect(DomainListUtility.hasEntryLongerThan('a.com\nb.com', 10)).toBe(false)
    })

    it('answers false at exactly the bound', () => {
        expect(DomainListUtility.hasEntryLongerThan('a'.repeat(10), 10)).toBe(false)
    })

    it('answers true one character past it', () => {
        expect(DomainListUtility.hasEntryLongerThan('a'.repeat(11), 10)).toBe(true)
    })

    it('finds an oversized entry among short ones', () => {
        expect(DomainListUtility.hasEntryLongerThan('a.com\n' + 'x'.repeat(300), 253)).toBe(true)
    })
})
