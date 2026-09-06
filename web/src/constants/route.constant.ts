/** Where the app can navigate, and the one parameter it carries between its pages. */

export const ROUTE = {
    scanForm: '/',
    multiScanResults: '/multi-scan-results',
} as const

export const DOMAINS_SEARCH_PARAMETER = 'domains'

export const buildDomainRoute = (domain: string): string => {
    return `/domain/${encodeURIComponent(domain)}`
}
