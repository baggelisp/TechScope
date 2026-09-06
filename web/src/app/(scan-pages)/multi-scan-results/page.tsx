import { redirect } from 'next/navigation'

import ScanResultsView from './_components/ScanResultsView'
import { buildDomainRoute, DOMAINS_SEARCH_PARAMETER, ROUTE } from '@/constants/route.constant'
import DomainListUtility from '@/utils/DomainListUtility'
import ScanDestinationUtility from '@/utils/ScanDestinationUtility'

type ScanResultsPageProps = {
    searchParams: Promise<Record<string, string | string[] | undefined>>
}

/**
 * Which page this URL really is.
 *
 * A list belongs on the matrix; one domain belongs on its own page, whether it was typed on the
 * form or arrived as a shared link. The scan itself is in the view below, so this reads as the
 * routing decision it is.
 */
const ScanResultsPage = async ({ searchParams }: ScanResultsPageProps) => {
    const parameters = await searchParams
    const domains = DomainListUtility.parse(decideDomainsText(parameters))
    const only = ScanDestinationUtility.decideSingleDomainOrNull(domains)

    if (only) redirect(buildDomainRoute(only))

    if (domains.length > 0) return <ScanResultsView domains={domains} />

    redirect(ROUTE.scanForm)
}

export default ScanResultsPage

function decideDomainsText(parameters: Record<string, string | string[] | undefined>): string {
    const written = parameters[DOMAINS_SEARCH_PARAMETER]

    if (typeof written === 'string') return written

    if (Array.isArray(written)) return written.join('\n')

    return ''
}
