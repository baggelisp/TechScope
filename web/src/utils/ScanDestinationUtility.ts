/**
 * Where submitting a list of domains should land.
 *
 * One domain has no matrix worth drawing: a single row of a single column says less than the
 * page that lays that domain out in full. So one domain goes straight to its own page, and the
 * matrix is for the case it was built for. The results page applies the same rule to a URL
 * someone shared, so the two routes cannot disagree about where one domain belongs.
 */

import { DOMAINS_SEARCH_PARAMETER, ROUTE, buildDomainRoute } from '@/constants/route.constant'

const SINGLE_DOMAIN_COUNT = 1

class ScanDestinationUtility {
    static decideDestination(domains: string[]): string {
        const only = domains[0]

        if (domains.length === SINGLE_DOMAIN_COUNT && only) return buildDomainRoute(only)

        const search = new URLSearchParams({ [DOMAINS_SEARCH_PARAMETER]: domains.join('\n') })

        return `${ROUTE.multiScanResults}?${search.toString()}`
    }

    static decideSingleDomainOrNull(domains: string[]): string | null {
        const only = domains[0]

        if (domains.length === SINGLE_DOMAIN_COUNT && only) return only

        return null
    }
}

export default ScanDestinationUtility
