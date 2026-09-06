import { describe, expect, it } from 'vitest'

import type { DomainResult, ScanReport } from '@/api/schemas'
import ScanReportUtility from '@/utils/ScanReportUtility'

const buildDomain = (overrides: Partial<DomainResult>): DomainResult => ({
    domain: 'a.com',
    observed_url: null,
    duration_seconds: 1,
    technologies: [],
    detections: [],
    problems: [],
    ...overrides,
})

const buildReport = (domains: DomainResult[]): ScanReport => ({
    summary: {
        domains: domains.length,
        detections: 0,
        domains_with_problems: 0,
        duration_seconds: 0,
    },
    domains,
})

describe('ScanReportUtility.listTechnologyNames', () => {
    it('returns nothing for a report with no domains', () => {
        expect(ScanReportUtility.listTechnologyNames(buildReport([]))).toEqual([])
    })

    it('returns nothing when nothing was detected', () => {
        expect(ScanReportUtility.listTechnologyNames(buildReport([buildDomain({})]))).toEqual([])
    })

    it('sorts and de-duplicates across domains', () => {
        const report = buildReport([
            buildDomain({ domain: 'a.com', technologies: ['Stripe', 'Cloudflare'] }),
            buildDomain({ domain: 'b.com', technologies: ['Cloudflare'] }),
        ])

        expect(ScanReportUtility.listTechnologyNames(report)).toEqual(['Cloudflare', 'Stripe'])
    })
})

describe('ScanReportUtility.decideDetectionOrNull', () => {
    it('answers null when the technology was not detected', () => {
        expect(ScanReportUtility.decideDetectionOrNull(buildDomain({}), 'Stripe')).toBeNull()
    })

    it('answers the detection when it was', () => {
        const domain = buildDomain({
            detections: [{ name: 'Stripe', confidence: 100, evidence: [] }],
        })

        expect(ScanReportUtility.decideDetectionOrNull(domain, 'Stripe')?.name).toBe('Stripe')
    })
})

describe('ScanReportUtility.listTroubledDomains', () => {
    it('returns nothing when every domain answered cleanly', () => {
        expect(ScanReportUtility.listTroubledDomains(buildReport([buildDomain({})]))).toEqual([])
    })

    it('returns only the domains that reported a problem', () => {
        const troubled = buildDomain({
            domain: 'b.com',
            problems: [{ collector: 'http', reason: 'timeout', detail: 'no response' }],
        })
        const report = buildReport([buildDomain({}), troubled])

        expect(ScanReportUtility.listTroubledDomains(report)).toEqual([troubled])
    })
})

describe('ScanReportUtility.buildSummaryOutput', () => {
    it('answers an empty object for an empty report', () => {
        expect(ScanReportUtility.buildSummaryOutput(buildReport([]))).toEqual({})
    })

    it('keeps a domain that detected nothing, as an empty list', () => {
        const report = buildReport([buildDomain({ domain: 'loom.com' })])

        expect(ScanReportUtility.buildSummaryOutput(report)).toEqual({ 'loom.com': [] })
    })

    it('is the shape the assignment asks for', () => {
        const report = buildReport([
            buildDomain({ domain: 'a.com', technologies: ['Cloudflare', 'Stripe'] }),
        ])

        expect(ScanReportUtility.buildSummaryOutput(report)).toEqual({
            'a.com': ['Cloudflare', 'Stripe'],
        })
    })
})
