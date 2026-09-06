/**
 * The boundary with the scanner's HTTP API.
 *
 * Nothing downstream trusts the network: every response is parsed here first, and the types the
 * rest of the app uses are inferred from these schemas rather than written twice. The string
 * values mirror the Python enums exactly, because the API is the contract.
 */

import { z } from 'zod'

export const CHANNEL = {
    header: 'header',
    cookie: 'cookie',
    scriptSrc: 'script_src',
    scriptInline: 'script_inline',
    html: 'html',
    meta: 'meta',
    jsGlobal: 'js_global',
    dnsMx: 'dns_mx',
    dnsTxt: 'dns_txt',
    dnsCname: 'dns_cname',
} as const

export type Channel = (typeof CHANNEL)[keyof typeof CHANNEL]

export const evidenceSchema = z.object({
    channel: z.string(),
    key: z.string().nullable(),
    pattern: z.string(),
    matched: z.string(),
})

export const detectionSchema = z.object({
    name: z.string(),
    confidence: z.number(),
    evidence: z.array(evidenceSchema),
})

export const problemSchema = z.object({
    collector: z.string(),
    reason: z.string(),
    detail: z.string(),
})

export const domainResultSchema = z.object({
    domain: z.string(),
    observed_url: z.string().nullable(),
    duration_seconds: z.number().nullable(),
    technologies: z.array(z.string()),
    detections: z.array(detectionSchema),
    problems: z.array(problemSchema),
})

export const scanSummarySchema = z.object({
    domains: z.number(),
    detections: z.number(),
    domains_with_problems: z.number(),
    duration_seconds: z.number(),
})

export const scanReportSchema = z.object({
    summary: scanSummarySchema,
    domains: z.array(domainResultSchema),
})

export const apiErrorSchema = z.object({
    error: z.object({
        code: z.string(),
        message: z.string(),
    }),
})

export type Evidence = z.infer<typeof evidenceSchema>
export type Detection = z.infer<typeof detectionSchema>
export type Problem = z.infer<typeof problemSchema>
export type DomainResult = z.infer<typeof domainResultSchema>
export type ScanSummary = z.infer<typeof scanSummarySchema>
export type ScanReport = z.infer<typeof scanReportSchema>
